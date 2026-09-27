#!/usr/bin/env python3
"""plan_shipped.py — the shipped-phase records' read model and staging check
(``skills/_shared/plan-shipped-phases.md``).

A story or single-issue plan grows on every revise and can never shrink by retirement the way an
epic plan does: a shipped phase is pushed but not yet evaluated, and the evaluator judges the WHOLE
PR diff against the plan's ``## Changes`` / ``## Data model / schema impact`` / ``## Test plan``.
So on every revise those sections' entries for each shipped phase MOVE — verbatim, never
re-authored — into one comment per phase, keyed ``(PR, phase)``. The main plan comment keeps
everything else, including every ``## Phases`` entry. This is the #41 delivery-log split applied to
the plan: an artifact that grows by construction becomes one bounded comment per unit.

Two surfaces:

- **The read model** (import-only, pure — never prints, exits or raises): :func:`collect` resolves
  the records for one PR out of an already-fetched thread (a thread scan, zero extra ``gh`` calls,
  for the same reason ``delivery_log.py`` scans: ``gh_gather``'s ``marker_prefix`` is a single-match
  lookup), and :func:`to_relocate` names the ticked code-shipping phases that have no record yet —
  exactly what a revise must move, so the planner never derives it.
- **``check``** (CLI): run by the planner after staging a revise. Reports the staged main body's
  size against the platform cap, and whether every relocated entry is a verbatim move of the prior
  plan's text, removed from main, and replaced there by a pointer bullet. Findings are the planner's
  to fix before persisting (the ``PHASES_MALFORMED`` posture) — ``ok`` always, no decision code.

Usage:
    plan_shipped.py check <prior-plan> <new-main> [<record> ...]
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipelib.decisions import MARKER_AMBIGUOUS, needs_decision  # noqa: E402
from pipelib.envelope import EXIT_OK, EXIT_USAGE_ERROR, emit_ok  # noqa: E402
from pipelib.limits import BODY_CHAR_LIMIT  # noqa: E402

# A distinct marker FAMILY, deliberately: `<!-- implementation-plan-shipped:` never starts with
# `<!-- implementation-plan:v1 -->`, so every existing plan lookup (gh_gather's `startswith`, the
# resolver audit's jq) stays blind to the records — no MARKER_AMBIGUOUS on the plan itself.
# `:phase:1 -->` is not a prefix of `:phase:10 -->`: the trailing ` -->` terminates the match.
MARKER_PREFIX = "<!-- implementation-plan-shipped:v1:phase:"
MARKER_SUFFIX = " -->"

_MARKER_RE = re.compile(re.escape(MARKER_PREFIX) + r"(\d+)" + re.escape(MARKER_SUFFIX))

# Line 2 carries the rest of the key. The PR number scopes a record to the PR its phase shipped on:
# a HARD Start-fresh closes that PR, and its records go inert without any delete.
_SHIPPED_ON_RE = re.compile(r"^\*\*Shipped on:\*\*\s+#(\d+)\s+·\s+Phase\s+(\d+)\s+—\s+(\S.*?)\s*$")

# The main plan's pointer bullet — it stands in for the moved entries and keeps an emptied heading
# parseable. No `@<sha>` in it: `_extract_plan_sha` is an unanchored first-match search.
_POINTER_RE = re.compile(
    r"^- Phases? [0-9][0-9, –-]*(?: and [0-9]+)? shipped on #(\d+): entries in the shipped-phase records\.$"
)

# The three sections whose entries move. Everything else stays in the main plan.
SECTIONS = (
    ("changes", r"Changes \(file-level\)"),
    ("data_model", r"Data model / schema impact"),
    ("test_plan", r"Test plan"),
)

_HEADING_RE = re.compile(r"^##(?!#)")
_BULLET_RE = re.compile(r"^(\s*)[-*] ")


def entry_marker(phase_number):
    """The record marker line for ``phase_number``. The single place this string is built."""
    return "%s%s%s" % (MARKER_PREFIX, phase_number, MARKER_SUFFIX)


def parse_head(body):
    """``(phase, pr, title)`` from a record body's first two lines, or ``None`` when line 1 is not a
    record marker. ``(phase, None, None)`` when line 1 is a marker but line 2 is missing, malformed,
    or names a different phase — a record that cannot be keyed."""
    lines = (body or "").split("\n")
    marker = _MARKER_RE.fullmatch(lines[0].strip()) if lines else None
    if marker is None:
        return None
    phase = int(marker.group(1))
    shipped_on = _SHIPPED_ON_RE.match(lines[1].strip()) if len(lines) > 1 else None
    if shipped_on is None or int(shipped_on.group(2)) != phase:
        return phase, None, None
    return phase, int(shipped_on.group(1)), shipped_on.group(3)


def comment_rest_id(comment):
    """A thread-located comment's REST **numeric** id (``databaseId``) — the id space every REST
    comment endpoint addresses (#34). Same rule as ``delivery_log.comment_rest_id``."""
    if comment is None:
        return None
    return comment.get("databaseId", comment.get("id"))


def collect(thread_list, pr_number):
    """Resolve the shipped-phase records for ``pr_number`` from an issue's comment thread.

    Returns ``(records, decision)``. ``decision`` is ``MARKER_AMBIGUOUS`` when one phase carries more
    than one record on this PR; that phase is omitted (its content is exactly what is unknown) and
    every other phase still resolves. Records on other PRs are counted, never returned — they belong
    to a PR a Start-fresh closed.

    ``records`` keys: ``present``, ``pr``, ``entries`` (``{phase, title, comment_id, comment_url}``
    in phase order), ``phases``, ``other_pr_entries``, ``unkeyed`` (``{comment_id, comment_url}`` of
    record-marked comments whose line 2 cannot be read), ``duplicated_phases``, ``text`` (every
    record body, phase order, for staging to one path), ``text_chars``.
    """
    by_phase = {}
    other_pr = 0
    unkeyed = []
    for comment in thread_list or []:
        head = parse_head((comment or {}).get("body"))
        if head is None:
            continue
        phase, pr, title = head
        if pr is None:
            unkeyed.append({"comment_id": comment_rest_id(comment), "comment_url": comment.get("url")})
            continue
        if pr_number is None or pr != int(pr_number):
            other_pr += 1
            continue
        by_phase.setdefault(phase, []).append((comment, title))

    duplicated = sorted(phase for phase, hits in by_phase.items() if len(hits) > 1)
    decision = None
    if duplicated:
        phase = duplicated[0]
        clashing = [comment for comment, _ in by_phase[phase]]
        decision = needs_decision(
            MARKER_AMBIGUOUS,
            summary="%d shipped-phase records name phase %s on PR #%s — expected at most one"
            % (len(clashing), phase, pr_number),
            context={
                "marker_prefix": entry_marker(phase),
                "pr": pr_number,
                "phase": phase,
                "duplicated_phases": duplicated,
                "comment_ids": [comment_rest_id(c) for c in clashing],
                "comment_urls": [c.get("url") for c in clashing],
            },
            options=[
                "inspect each comment and pick the one to treat as current",
                "delete the stale duplicate comment(s), then re-run",
            ],
        )

    entries = []
    bodies = []
    for phase in sorted(p for p, hits in by_phase.items() if len(hits) == 1):
        comment, title = by_phase[phase][0]
        entries.append(
            {
                "phase": phase,
                "title": title,
                "comment_id": comment_rest_id(comment),
                "comment_url": comment.get("url"),
            }
        )
        bodies.append((comment.get("body") or "").strip())
    text = "\n\n".join(bodies)
    records = {
        "present": bool(entries),
        "pr": pr_number,
        "entries": entries,
        "phases": [entry["phase"] for entry in entries],
        "other_pr_entries": other_pr,
        "unkeyed": unkeyed,
        "duplicated_phases": duplicated,
        "text": text,
        "text_chars": len(text),
    }
    return records, decision


def to_relocate(phases, tracker_rows, recorded_phases):
    """The ticked, code-shipping phases with no record yet — what this revise must move.

    ``phases`` is ``parse.parse_phases`` output (``None`` when the prior plan did not parse: nothing
    can be attributed, so nothing is proposed). ``tracker_rows`` is the PR's parsed ``## Phase
    tracker``; only main rows count (a ``Phase <N>-<label>`` sub-row is bound to its phase, not a
    tick of it). An ``operator`` / ``decision-only`` phase has no entries to move, so it is never
    proposed — otherwise it would reappear on every revise.
    """
    if not phases:
        return []
    ticked = {row["phase"] for row in tracker_rows or [] if row.get("checked") and row.get("sub_label") is None}
    code_shipping = {phase["number"] for phase in phases if phase.get("kind") == "code-shipping"}
    recorded = set(recorded_phases or [])
    return sorted((ticked & code_shipping) - recorded)


# ---------------------------------------------------------------------------------------------
# `check` — the staging gate's facts
# ---------------------------------------------------------------------------------------------


def _section_lines(lines, heading_pattern):
    """The body lines of ``## <heading>`` (heading excluded; a trailing ``(…)`` annotation on the
    heading tolerated), or ``None`` when absent. Same section-finder shape as ``parse.py``."""
    heading_re = re.compile(r"^##\s+" + heading_pattern + r"\s*(?:\(.*\))?\s*$", re.IGNORECASE)
    for i, line in enumerate(lines):
        if heading_re.match(line):
            end = len(lines)
            for j in range(i + 1, len(lines)):
                if _HEADING_RE.match(lines[j]):
                    end = j
                    break
            return lines[i + 1:end]
    return None


def _blocks(section_lines):
    """Split a section into bullet blocks: a bullet line (any depth) plus its non-blank, non-bullet
    continuation lines. Returns ``[(indent, lines_tuple, first_line_number_in_section)]``. This is
    the unit ``check`` compares at — the same algorithm on both sides, so a boundary choice can
    never itself make a verbatim move look edited."""
    blocks = []
    current = None
    for number, raw in enumerate(section_lines or []):
        line = raw.rstrip()
        bullet = _BULLET_RE.match(line)
        if bullet:
            if current is not None:
                blocks.append(current)
            current = [len(bullet.group(1)), [line], number]
        elif line and current is not None:
            current[1].append(line)
        else:
            if current is not None:
                blocks.append(current)
            current = None
    if current is not None:
        blocks.append(current)
    return [(indent, tuple(body), number) for indent, body, number in blocks]


def _is_parent(blocks, index):
    """A block that the next block nests under. Only a `## Test plan` kind line (`- Unit:`) may
    legitimately stay in main while some of its children move, so only there is a parent exempt from
    the moved-not-copied check. A `## Changes` parent left in main with a child moved IS the split
    the shared-entry rule forbids — the unit there is the whole top-level bullet."""
    return index + 1 < len(blocks) and blocks[index + 1][0] > blocks[index][0]


def check(prior_text, main_text, records):
    """The staging facts for one revise. ``records`` is ``[(path, text)]``.

    Returns the payload dict. ``clean`` is true only when every finding list is empty and every body
    fits the cap.
    """
    prior_lines = prior_text.split("\n")
    main_lines = main_text.split("\n")

    findings = {
        "malformed_head": [],
        "unexpected_sections": [],
        "not_verbatim": [],
        "still_in_main": [],
        "missing_pointer": [],
        "record_over_limit": [],
    }
    record_facts = []
    moved_sections = set()
    record_prs = set()

    for path, text in records:
        head = parse_head(text)
        phase, pr = (head[0], head[1]) if head else (None, None)
        if head is None or pr is None:
            findings["malformed_head"].append(path)
        else:
            record_prs.add(pr)
        chars = len(text)
        if chars > BODY_CHAR_LIMIT:
            findings["record_over_limit"].append(path)
        lines = text.split("\n")
        known = [re.compile(r"^##\s+" + pattern + r"\s*(?:\(.*\))?\s*$", re.IGNORECASE) for _, pattern in SECTIONS]
        for line in lines:
            if _HEADING_RE.match(line) and not any(k.match(line) for k in known):
                findings["unexpected_sections"].append({"path": path, "heading": line.strip()})

        units = 0
        for key, pattern in SECTIONS:
            record_section = _section_lines(lines, pattern)
            if not record_section:
                continue
            record_blocks = _blocks(record_section)
            if not record_blocks:
                continue
            moved_sections.add(key)
            prior_blocks = {body for _, body, _ in _blocks(_section_lines(prior_lines, pattern))}
            main_blocks = {body for _, body, _ in _blocks(_section_lines(main_lines, pattern))}
            for index, (_, body, number) in enumerate(record_blocks):
                units += 1
                if body not in prior_blocks:
                    findings["not_verbatim"].append({"path": path, "section": key, "line": body[0]})
                elif body in main_blocks and not (key == "test_plan" and _is_parent(record_blocks, index)):
                    findings["still_in_main"].append({"path": path, "section": key, "line": body[0]})
        record_facts.append({"path": path, "phase": phase, "pr": pr, "chars": chars, "units": units})

    for key, pattern in SECTIONS:
        if key not in moved_sections:
            continue
        section = _section_lines(main_lines, pattern) or []
        pointer_prs = {int(m.group(1)) for m in (_POINTER_RE.match(l.rstrip()) for l in section) if m}
        if not pointer_prs or (record_prs and not record_prs <= pointer_prs):
            findings["missing_pointer"].append(key)

    main_chars = len(main_text)
    over_limit = main_chars > BODY_CHAR_LIMIT
    return {
        "main": {
            "chars": main_chars,
            "limit_chars": BODY_CHAR_LIMIT,
            "headroom_chars": BODY_CHAR_LIMIT - main_chars,
            "over_limit": over_limit,
        },
        "records": record_facts,
        "findings": findings,
        "clean": not over_limit and not any(findings.values()),
    }


def _read_or_die(path_str):
    try:
        return Path(path_str).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write("plan_shipped: cannot read %s: %s\n" % (path_str, exc))
        sys.exit(EXIT_USAGE_ERROR)


def main(argv):
    parser = argparse.ArgumentParser(prog="plan_shipped.py", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="subcommand")
    p_check = sub.add_parser("check")
    p_check.add_argument("prior_plan")
    p_check.add_argument("new_main")
    p_check.add_argument("records", nargs="*")
    if not argv:
        parser.print_usage(sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)
    args = parser.parse_args(argv)
    if args.subcommand != "check":
        parser.print_usage(sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)
    payload = check(
        _read_or_die(args.prior_plan),
        _read_or_die(args.new_main),
        [(path, _read_or_die(path)) for path in args.records],
    )
    emit_ok(payload=payload)
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main(sys.argv[1:])
