#!/usr/bin/env python3
"""config_block.py — deterministic, idempotent read/write of the marker-delimited configuration
blocks the github-pipeline skills consume (e.g. `<!-- issue-resolver-fast-checks -->` … `<!--
/issue-resolver-fast-checks -->`), under the architecture.md §3 envelope.

This is the S21 Python port of v1's ``scripts/config-block.sh`` — the v1 file is a frozen
behavioral reference (still used by v1 callers until S20) and is **not** edited by this port. The
behavior contract is preserved exactly, re-expressed in envelope terms: same subcommands, same
argument shape, same canonical block form, same idempotency/no-op guarantees, same nonexistent-
file handling, same duplicate/unterminated-marker refusals. What changes is the wire format: `read`
still prints a block's interior to stdout as raw text, `list` still prints `<status> <name>` lines
as raw text, and `upsert`/`remove` now emit an architecture.md §3 JSON envelope (`{"status": "ok",
...}` or `{"status": "needs_decision", ...}`) instead of v1's bare `{"op": ..., "changed": ...}`
object, plus proper usage-error exit code 2.

This module does **no** GitHub or git I/O and shells out to nothing — it only reads/writes local
Markdown files. `workspace.py` (§6) delegates block reads to it for `<!-- worktree-setup/teardown
-->` discovery; `skills/setup/` (v2 rename of `github-pipeline-setup`) uses it for all block I/O.

Canonical block form: the line ``<!-- NAME -->`` on its own line, the block's interior lines, and
the line ``<!-- /NAME -->`` on its own line — each delimiter tolerant of surrounding leading/
trailing whitespace on its line, matched only after trimming. ``<marker-name>`` is the bare name
without comment syntax (e.g. ``issue-resolver-fast-checks``), constrained to ``^[A-Za-z0-9:_-]+$``
so a stray name can never smuggle in comment syntax that would confuse the delimiter scan (v1's
same rule, restated in Python-native terms rather than as a regex fed to `awk`).

Subcommands:
    config_block.py read   <file> <marker-name>
    config_block.py list   <file>
    config_block.py upsert <file> <marker-name> <body-path> [--dry-run] [--prepend]
    config_block.py remove <file> <marker-name>             [--dry-run]

``read``/``list`` print raw text (not an envelope) on success, matching v1 exactly, so a caller can
capture a block's contents or the inventory directly:
    - `read` exit 0: interior lines to stdout, one per line, no trailing envelope.
    - `read` exit 3: the named block is absent (this **includes** a nonexistent file — v1 treats
      "file doesn't exist" as "block doesn't exist," not a distinct error; verified against v1
      directly rather than inferred from prose).
    - `read` exit 4: `MARKER_AMBIGUOUS` — the marker's delimiter appears more than once.
    - `read` exit 5: the marker is unterminated (open with no close) or closes before it opens.
    - `list` exit 0 always, even against a nonexistent file (empty stdout — "no file" is "no
      blocks," not an error, matching v1 and docs/specs/setup.md's explicit note on this).
      Prints one `<status> <name>` line per discovered marker name: `ok` (well-formed, matching
      close present), `open` (unterminated), `dup` (declared more than once).

``upsert``/``remove`` emit exactly one architecture.md §3 JSON envelope on stdout:
    - `upsert` ok: `{"status": "ok", "op": "upsert", "marker": ..., "file": ..., "changed": ...,
      "dry_run": ..., "body_bytes": ..., "body_sha256": ..., "notices": []}`.
    - `remove` ok: `{"status": "ok", "op": "remove", "marker": ..., "file": ..., "changed": ...,
      "dry_run": ..., "notices": []}` (no `body_bytes`/`body_sha256` — remove stages no body).
    - Either, on a duplicate marker where the contract expects one: `{"status": "needs_decision",
      "decision": {"code": "MARKER_AMBIGUOUS", ...}, "notices": []}`, exit 0 (`needs_decision` is
      a valid outcome, not an error, per architecture.md §3).
    - `changed: false` means the file is already in the desired state and was **not touched on
      disk at all** — not even its mtime — matching v1's `finish_write`'s `cmp -s` short-circuit
      exactly (this is the idempotency guarantee the whole script exists to make deterministic:
      re-running `upsert` with the same body is a byte-level no-op, never a model-landed edit that
      merely happens to reproduce the same bytes).

Exit codes (usage/malformed-input paths only — these are NOT envelope-carrying; architecture.md §3:
exit 2 means no envelope is emitted):
    2   usage error, invalid marker name (`INVALID_MARKER_NAME: ...` on stderr), or a missing
        staged body file for `upsert` (`MISSING_BODY_FILE: ...` on stderr) — v1's own usage-error
        exit code, preserved verbatim rather than folded into a decision (these are malformed
        *invocations*, not a state the operator resolves via a decision card).
    3   (`read` only) the named block is absent.
    4   the named marker appears more than once — surfaced as exit code for `read`, and as a
        `MARKER_AMBIGUOUS` needs_decision envelope (exit 0) for `upsert`/`remove`, since those two
        already emit an envelope and architecture.md §3's decision-code path is how they express
        "found a state only the operator can resolve."
    5   the named marker is unterminated / closes before it opens (`read` only — `upsert`/`remove`
        also refuse this shape, but v1 has no dedicated decision code for it distinct from
        malformed content, so it stays a bare exit 5 on all four subcommands for consistency with
        `read`, matching v1's own uniform treatment).

Marker discovery order: `list`'s per-name ordering is **not** part of the v1 contract — the
`.sh` implementation's order is `awk`'s associative-array iteration order (verified directly:
hash order, not file order, not alphabetical), an implementation artifact of that interpreter, not
a documented behavior. This port instead orders `list` output deterministically by each marker's
first line of first appearance in the file, so the same input always produces the same output
across runs and across platforms — a strictly stronger guarantee than v1 offered, and consistent
with "same output fields" (the fields are `status name`; the field *order* was never specified).
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipelib.decisions import MARKER_AMBIGUOUS, needs_decision  # noqa: E402
from pipelib.envelope import EXIT_OK, EXIT_USAGE_ERROR, emit_needs_decision, emit_ok  # noqa: E402
from pipelib.hashing import sha256_hex  # noqa: E402

# Exit codes not covered by pipelib.envelope's EXIT_OK / EXIT_USAGE_ERROR — v1-specific codes this
# port preserves verbatim (module docstring's "Exit codes" section).
EXIT_BLOCK_ABSENT = 3
EXIT_MARKER_AMBIGUOUS = 4
EXIT_MARKER_UNTERMINATED = 5

# Marker names are matched as literal strings (never as regex) against a trimmed line, but this
# constrains the *input* name anyway — v1's own rule, restated here rather than fed to `awk` as a
# string-interpolated comparison target — so a stray name can never smuggle in comment syntax that
# would confuse the delimiter scan.
_VALID_MARKER_NAME_RE = re.compile(r"^[A-Za-z0-9:_-]+$")

# The whole-line delimiter shape `list` scans for: an optional leading `/` (close), then the name,
# each tolerant of surrounding whitespace on the line (matched after `.strip()`, not by this
# regex's own anchors doing the trimming — see `_scan_all_marker_lines`).
_DELIMITER_LINE_RE = re.compile(r"^<!--\s*(/?)([A-Za-z0-9:_-]+)\s*-->$")


def _die_usage(parser):
    parser.print_usage(sys.stderr)
    sys.exit(EXIT_USAGE_ERROR)


def _validate_marker_name(name):
    """Exit 2 with `INVALID_MARKER_NAME: ...` on stderr if `name` fails the allowed-charset check
    — v1's `validate_name`, same message text and exit code (docstring's "Exit codes" table).
    """
    if not _VALID_MARKER_NAME_RE.match(name):
        sys.stderr.write("INVALID_MARKER_NAME: %s (allowed: A-Z a-z 0-9 : _ -)\n" % name)
        sys.exit(EXIT_USAGE_ERROR)


def _read_lines_or_empty(file_path):
    """Read `file_path` as a list of lines with trailing newlines stripped (each element is one
    logical line's content, matching `awk`'s `$0`/record semantics — v1's `AWK_SCAN` buffers every
    line into `lines[n]` the same way). Returns `[]` when the file does not exist, so `upsert`
    (which treats an absent file as empty input, per v1's `input="/dev/null"` fallback) and
    `remove`/`list`'s "no file ⇒ no blocks" degrade to the same empty-input path as a genuinely
    empty file, without special-casing existence at every call site.
    """
    path = Path(file_path)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    if text == "":
        return []
    # splitlines(keepends=False) drops the line terminators themselves; a trailing newline in the
    # source produces no phantom empty final element (matching `awk`'s per-record read, which
    # never yields a record for the text after a file's final "\n").
    return text.splitlines()


def _scan_marker(lines, name):
    """Re-implements v1's `AWK_SCAN` for one target `name`: returns `(open_count, close_count,
    open_index, close_index)`, all 0/None-safe 1-based indices into `lines` (1-based to mirror the
    awk source's `n`/`oi`/`ci` exactly, so the index arithmetic in `_render_*` below reads the same
    way as `run_upsert`/`run_remove` in the `.sh`).

    A line "is" an open/close delimiter for `name` after `.strip()` equals the exact string
    `<!-- NAME -->` / `<!-- /NAME -->` — literal string comparison, not the `_DELIMITER_LINE_RE`
    pattern (which is `list`'s tool for discovering *any* marker name present; a targeted scan for
    one already-known name only needs an exact-match compare, matching v1's `openm`/`closem`
    string-equality check exactly rather than re-deriving it through a name-extracting regex).
    """
    open_marker = "<!-- %s -->" % name
    close_marker = "<!-- /%s -->" % name
    open_count = close_count = 0
    open_index = close_index = 0
    for i, raw_line in enumerate(lines, start=1):
        trimmed = raw_line.strip()
        if trimmed == open_marker:
            open_count += 1
            if open_index == 0:
                open_index = i
        elif trimmed == close_marker:
            close_count += 1
            if close_index == 0:
                close_index = i
    return open_count, close_count, open_index, close_index


def _read_body_lines(body_path):
    """Read the staged body file as a list of lines (trailing newlines stripped), matching v1's
    `emit_body()` — which streams the body file line-by-line via `getline` and re-adds one newline
    per line, canonicalizing whatever trailing-newline state the body file is in (present, absent,
    or a body with embedded blank lines) so the append path and the replace path always produce
    identical interior bytes regardless of how the caller staged the file.
    """
    with open(body_path, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()
    if text == "":
        return []
    return text.splitlines()


# ---- read ----


def run_read(args):
    """`read <file> <marker-name>` — print the block's interior to stdout, one line per source
    line, no trailing envelope (module docstring). Exit 3 if absent (including a nonexistent
    file — verified directly against v1, not inferred), 4 if ambiguous, 5 if unterminated/
    inverted.
    """
    _validate_marker_name(args.marker_name)
    lines = _read_lines_or_empty(args.file)
    open_count, close_count, open_index, close_index = _scan_marker(lines, args.marker_name)
    if open_count == 0:
        sys.exit(EXIT_BLOCK_ABSENT)
    if open_count > 1 or close_count > 1:
        sys.exit(EXIT_MARKER_AMBIGUOUS)
    if open_count != close_count or close_index < open_index:
        sys.exit(EXIT_MARKER_UNTERMINATED)
    interior = lines[open_index:close_index - 1]  # lines is 0-indexed; open_index/close_index are 1-based
    out_lines = [line + "\n" for line in interior]
    sys.stdout.write("".join(out_lines))
    sys.exit(EXIT_OK)


# ---- list ----


def run_list(args):
    """`list <file>` — print `<status> <name>` per discovered marker, one per line, ordered by
    first line of first appearance (module docstring's "Marker discovery order" note — v1's own
    order is unspecified `awk` hash order, not a contract this port needs to reproduce). Exit 0
    always, even against a nonexistent file (empty stdout).
    """
    lines = _read_lines_or_empty(args.file)
    open_counts = {}
    close_counts = {}
    first_seen_at = {}
    for i, raw_line in enumerate(lines, start=1):
        trimmed = raw_line.strip()
        match = _DELIMITER_LINE_RE.match(trimmed)
        if not match:
            continue
        is_close, name = match.group(1) == "/", match.group(2)
        if name not in first_seen_at:
            first_seen_at[name] = i
        if is_close:
            close_counts[name] = close_counts.get(name, 0) + 1
        else:
            open_counts[name] = open_counts.get(name, 0) + 1

    ordered_names = sorted(open_counts.keys(), key=lambda n: first_seen_at[n])
    out_lines = []
    for name in ordered_names:
        opens = open_counts[name]
        closes = close_counts.get(name, 0)
        if opens > 1:
            status = "dup"
        elif closes >= 1:
            status = "ok"
        else:
            status = "open"
        out_lines.append("%s %s\n" % (status, name))
    sys.stdout.write("".join(out_lines))
    sys.exit(EXIT_OK)


# ---- shared render for upsert's four placement shapes ----


def _render_upsert(lines, name, body_lines, prepend):
    """Re-implements v1's `run_upsert` awk `END` block: given the existing file's `lines`, the
    target marker `name`, the staged `body_lines`, and whether a *newly created* block should be
    prepended, return the new full line list — or raise `_MarkerAmbiguous` / `_MarkerUnterminated`
    on the same malformed-input shapes v1 refuses rather than guesses through.

    Four placement shapes, matching v1 exactly:
      1. An existing well-formed block: body replaces the interior in place, position unchanged.
      2. No existing block, `prepend=True`: new block at the very top, then one blank line (only
         if the file has content — `n>0 and trim(lines[1])!=""` in v1), then the original content.
      3. No existing block, `prepend=False` (default): original content, then one blank line (only
         if the file has content and its last line is non-blank), then the new block appended.
      (Shape 4 — `oc>1` — is not a placement shape; it's the ambiguity refusal below.)
    """
    open_count, close_count, open_index, close_index = _scan_marker(lines, name)
    if open_count > 1 or close_count > 1:
        raise _MarkerAmbiguous()
    if open_count != close_count:
        raise _MarkerUnterminated()

    open_marker = "<!-- %s -->" % name
    close_marker = "<!-- /%s -->" % name

    if open_count == 1:
        if close_index < open_index:
            raise _MarkerUnterminated()
        # Up to and including the open delimiter, then the body, then the close delimiter onward —
        # v1's `for(i=1;i<=oi;i++) ... emit_body() ... for(i=ci;i<=n;i++)`.
        return lines[:open_index] + body_lines + lines[close_index - 1:]

    if prepend:
        new_block = [open_marker] + body_lines + [close_marker]
        if lines and lines[0].strip() != "":
            return new_block + [""] + lines
        return new_block + lines

    new_block = [open_marker] + body_lines + [close_marker]
    if lines and lines[-1].strip() != "":
        return lines + [""] + new_block
    return lines + new_block


def _render_remove(lines, name):
    """Re-implements v1's `run_remove` awk `END` block: return `(new_lines, changed)`.

    `changed=False` with `new_lines` equal to the input means the block was already absent — v1's
    `if(oc==0){ ...; exit 0 }` branch, which the caller (`run_remove`) uses to skip the
    write/envelope machinery's dry-run/no-op distinction entirely (v1 short-circuits to the
    envelope before even invoking `finish_write`'s `cmp`, since it already knows nothing changed).
    """
    open_count, close_count, open_index, close_index = _scan_marker(lines, name)
    if open_count == 0:
        return lines, False
    if open_count > 1 or close_count > 1:
        raise _MarkerAmbiguous()
    if open_count != close_count or close_index < open_index:
        raise _MarkerUnterminated()
    drop_start = open_index
    if open_index > 1 and lines[open_index - 2].strip() == "":  # one blank line above, if present
        drop_start = open_index - 1
    new_lines = [
        line for i, line in enumerate(lines, start=1) if not (drop_start <= i <= close_index)
    ]
    return new_lines, True


class _MarkerAmbiguous(Exception):
    """Internal signal: the target marker's delimiter appears more than once — caught by the
    `upsert`/`remove` command handlers and turned into a `MARKER_AMBIGUOUS` needs_decision
    envelope (module docstring). Never escapes this module.
    """


class _MarkerUnterminated(Exception):
    """Internal signal: the target marker is open with no matching close, or closes before it
    opens — caught by the `upsert`/`remove` command handlers and turned into exit 5 (module
    docstring: "v1 has no dedicated decision code for it distinct from malformed content").
    """


def _serialize(lines):
    """Join a line list back into file text: one trailing newline per line, matching both v1's
    `print` (which always appends `ORS`, default `"\\n"`) and `_read_lines_or_empty`'s
    `splitlines()` (which drops terminators) — so a round-trip through this module's own
    read → render → serialize path reproduces the source bytes exactly when nothing changed, and
    an empty `lines` list serializes to `""` (an empty file), not a single stray newline.
    """
    return "".join(line + "\n" for line in lines)


# ---- upsert ----


def run_upsert(args):
    _validate_marker_name(args.marker_name)
    body_path = Path(args.body_path)
    if not body_path.is_file():
        sys.stderr.write("MISSING_BODY_FILE: %s\n" % args.body_path)
        sys.exit(EXIT_USAGE_ERROR)

    file_path = Path(args.file)
    existing_lines = _read_lines_or_empty(args.file)
    body_lines = _read_body_lines(body_path)

    try:
        new_lines = _render_upsert(existing_lines, args.marker_name, body_lines, args.prepend)
    except _MarkerAmbiguous:
        decision = needs_decision(
            MARKER_AMBIGUOUS,
            summary="marker '%s' appears more than once in %s" % (args.marker_name, args.file),
            context={"op": "upsert", "marker": args.marker_name, "file": args.file},
            options=["resolve the duplicate block by hand, then re-run"],
        )
        emit_needs_decision(decision)
        sys.exit(EXIT_OK)
    except _MarkerUnterminated:
        sys.exit(EXIT_MARKER_UNTERMINATED)

    new_text = _serialize(new_lines)
    old_text = _serialize(existing_lines) if file_path.exists() else None
    changed = old_text != new_text

    if changed and not args.dry_run:
        with open(file_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(new_text)
    # changed=False (or dry_run=True): the target file is left byte-for-byte untouched — not even
    # opened for writing — matching v1's `finish_write`, which only ever `mv`s the temp file over
    # the real one inside that same guard (module docstring's `changed: false` note).

    with open(body_path, "rb") as fh:
        body_bytes_data = fh.read()

    payload = {
        "op": "upsert",
        "marker": args.marker_name,
        "file": args.file,
        "changed": changed,
        "dry_run": args.dry_run,
        "body_bytes": len(body_bytes_data),
        "body_sha256": sha256_hex(body_bytes_data),
    }
    emit_ok(payload=payload)
    sys.exit(EXIT_OK)


# ---- remove ----


def run_remove(args):
    _validate_marker_name(args.marker_name)
    file_path = Path(args.file)

    if not file_path.exists():
        # Nothing to remove — report a no-op without inventing a file (v1's identical short-
        # circuit: `[[ ! -f "$file" ]]` returns before ever building a temp file).
        payload = {
            "op": "remove",
            "marker": args.marker_name,
            "file": args.file,
            "changed": False,
            "dry_run": args.dry_run,
        }
        emit_ok(payload=payload)
        sys.exit(EXIT_OK)

    existing_lines = _read_lines_or_empty(args.file)
    try:
        new_lines, changed = _render_remove(existing_lines, args.marker_name)
    except _MarkerAmbiguous:
        decision = needs_decision(
            MARKER_AMBIGUOUS,
            summary="marker '%s' appears more than once in %s" % (args.marker_name, args.file),
            context={"op": "remove", "marker": args.marker_name, "file": args.file},
            options=["resolve the duplicate block by hand, then re-run"],
        )
        emit_needs_decision(decision)
        sys.exit(EXIT_OK)
    except _MarkerUnterminated:
        sys.exit(EXIT_MARKER_UNTERMINATED)

    if changed and not args.dry_run:
        with open(file_path, "w", encoding="utf-8", newline="") as fh:
            fh.write(_serialize(new_lines))
    # changed=False (absent block): file is left byte-for-byte untouched, same guard as upsert.

    payload = {
        "op": "remove",
        "marker": args.marker_name,
        "file": args.file,
        "changed": changed,
        "dry_run": args.dry_run,
    }
    emit_ok(payload=payload)
    sys.exit(EXIT_OK)


# ---- dispatch ----


def build_parser():
    parser = argparse.ArgumentParser(
        prog="config_block.py",
        description="Deterministic marker-block read/write (architecture.md §3, §6).",
    )
    sub = parser.add_subparsers(dest="subcommand")

    p_read = sub.add_parser("read")
    p_read.add_argument("file")
    p_read.add_argument("marker_name")

    p_list = sub.add_parser("list")
    p_list.add_argument("file")

    p_upsert = sub.add_parser("upsert")
    p_upsert.add_argument("file")
    p_upsert.add_argument("marker_name")
    p_upsert.add_argument("body_path")
    p_upsert.add_argument("--dry-run", dest="dry_run", action="store_true")
    p_upsert.add_argument("--prepend", dest="prepend", action="store_true")

    p_remove = sub.add_parser("remove")
    p_remove.add_argument("file")
    p_remove.add_argument("marker_name")
    p_remove.add_argument("--dry-run", dest="dry_run", action="store_true")

    return parser


def main(argv):
    parser = build_parser()
    if not argv:
        _die_usage(parser)
    args = parser.parse_args(argv)
    if args.subcommand is None:
        _die_usage(parser)

    if args.subcommand == "read":
        run_read(args)
    elif args.subcommand == "list":
        run_list(args)
    elif args.subcommand == "upsert":
        run_upsert(args)
    elif args.subcommand == "remove":
        run_remove(args)
    else:
        _die_usage(parser)  # pragma: no cover — argparse's own `choices` already excludes this


if __name__ == "__main__":
    main(sys.argv[1:])
