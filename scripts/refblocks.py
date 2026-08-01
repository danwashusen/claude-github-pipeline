"""refblocks.py — ref-pinned config-block reading (architecture.md §6's v3 gate-config rule).

Import-only module (no shebang, no ``main`` — composed in-process by the preps and by
``workspace.py``'s attach path, never dispatched; ``oq_tracker.py`` is the precedent). It is the
v3 replacement for reading gate config out of a trusted root *checkout*: instead of asserting the
root working tree is clean-on-main and then plain-``open()``-ing its files (the v2 shape, which
carried a TOCTOU window between the freshness check and the reads), a prep pins ``origin/main``
ONCE (``fetch_pin``) and reads every block from that commit's **blobs** via ``git show`` — no
checkout involved, so the result is identical no matter where the session sits and no matter what
any working tree contains. This is what keeps "a PR cannot weaken its own gates" true after the
workspace-model inversion put sessions *inside* PR-branch worktrees.

Discipline: **pin once, read many.** Call :func:`fetch_pin` exactly once per prep and thread the
returned SHA through every :func:`read_block_at_ref` call — all reads then address one immutable
commit, so a concurrent push between reads can never split the config view.

``config_block.py`` keeps its documented "no git by design" purity: this module composes its pure
scan primitives (``_scan_marker``, ``extract_include_tokens``) over blob text fetched here via
``pipelib.process`` (git only). The discovery semantics mirror ``config_block.read_block_anywhere``
byte-for-byte — ``COMMANDS.md`` then ``CLAUDE.md`` then one level of ``@``-includes, first present
well-formed block wins, malformed-in-one-candidate == absent-there — just resolved at a ref
instead of on disk.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config_block  # noqa: E402  (in-process composition of the pure scan primitives)
from pipelib import process  # noqa: E402

PIN_BRANCH = "main"


def _git(argv, cwd):
    return process.run(["git"] + list(argv), cwd=str(cwd))


def fetch_pin(root, branch=PIN_BRANCH):
    """``git fetch origin <branch>`` (cwd = ``root``), then return the full 40-hex SHA of
    ``origin/<branch>`` — the session's config pin. A fetch or rev-parse failure is a hard failure
    (faithful stderr, ``sys.exit(1)``, no envelope — architecture.md §3's exit-code contract):
    gate config read from an unknown or stale pin is worse than no session at all.
    """
    fetch_result = _git(["fetch", "origin", branch], root)
    if fetch_result.returncode != 0:
        sys.stderr.write(fetch_result.stderr)
        sys.exit(1)
    rev_result = _git(["rev-parse", "origin/%s" % branch], root)
    if rev_result.returncode != 0:
        sys.stderr.write(rev_result.stderr)
        sys.exit(1)
    return rev_result.stdout.strip()


def read_lines_at_ref(root, sha, rel_path):
    """``git show <sha>:<rel_path>`` -> list of lines (``splitlines()``, trailing newlines
    stripped — matching ``config_block._read_lines_or_empty``'s record semantics). Returns
    ``None`` when the path does not exist at the ref (git's non-zero exit), the at-ref analogue of
    ``_read_lines_or_empty``'s missing-file ``[]`` — ``None`` (not ``[]``) so a caller can still
    distinguish "absent at ref" from "present but empty" where it matters.
    """
    result = _git(["show", "%s:%s" % (sha, rel_path)], root)
    if result.returncode != 0:
        return None
    return result.stdout.splitlines()


def candidate_files_at_ref(root, sha, candidate_filenames=config_block.DEFAULT_CONFIG_CANDIDATE_FILES):
    """Ordered candidate list for at-ref config-block discovery, as repo-relative paths:
    ``candidate_filenames`` (default ``COMMANDS.md``, ``CLAUDE.md``), then every path either one
    ``@``-includes (one level), with the include text itself read at the ref. An absolute include
    path cannot name a repo blob, so it is skipped (the working-tree loop resolves those against
    the filesystem instead — a divergence that cannot matter here, since an absolute path is by
    definition outside the pinned commit's tree).
    """
    candidates = list(candidate_filenames)
    for root_file in list(candidates):
        lines = read_lines_at_ref(root, sha, root_file)
        if lines is None:
            continue
        for token in config_block.extract_include_tokens("\n".join(lines)):
            if Path(token).is_absolute():
                continue
            candidates.append(token)
    return candidates


def read_block_at_ref(root, sha, marker_name, candidate_filenames=config_block.DEFAULT_CONFIG_CANDIDATE_FILES):
    """Read the first well-formed ``<!-- marker_name -->`` block across the candidate files **at
    the pinned ref** — the at-ref rendering of ``config_block.read_block_anywhere``: first
    present, well-formed block wins; a malformed block (duplicate/unterminated) in one candidate
    is treated exactly like an absent one — try the next candidate (the closed decision-code set
    has no malformed-block code).

    Returns ``(present, interior_lines, source_or_none)`` where ``source`` is
    ``"<sha7>:<rel_path>"`` — the provenance string a facts block can carry so an operator can see
    exactly which blob the config came from.
    """
    for rel_path in candidate_files_at_ref(root, sha, candidate_filenames=candidate_filenames):
        lines = read_lines_at_ref(root, sha, rel_path)
        if lines is None:
            continue
        open_count, close_count, open_index, close_index = config_block._scan_marker(lines, marker_name)
        if open_count == 0:
            continue
        if open_count > 1 or close_count > 1:
            continue
        if open_count != close_count or close_index < open_index:
            continue
        interior = lines[open_index : close_index - 1]
        return True, interior, "%s:%s" % (sha[:7], rel_path)
    return False, [], None
