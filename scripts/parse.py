#!/usr/bin/env python3
"""parse.py — the single parser for the shared GitHub body grammars (architecture.md §2, §3;
docs/implementation.md S5), ending the per-skill prompt-side parsing v1 did inline in each
`SKILL.md`. This is a from-scratch v2 script: there is no v1 `parse.py` to port from — v1 skills
parsed these grammars as an implicit reading step inside the prompt itself, which is exactly what
this script exists to replace with a deterministic, testable implementation.

File I/O only. No `gh`, no `git`, no network, no subprocess of any kind — every subcommand reads
one already-materialized file path from local disk and emits one architecture.md §3 envelope on
stdout. Callers (prep scripts, playbooks) are responsible for getting the body onto disk first
(a `gh_gather.py` result's `*_path`, or any other already-staged file); this module never fetches
anything itself.

Subcommands, each `<subcommand> <body-file>`:

    parse.py dod <body-file> [--render]
        Parses the `## Definition of done` section's top-level checkbox bullets per
        `skills/_shared/dod-annotations.md`'s closed set of five annotation forms (plus the
        "no annotation" bare bullet). `ok` payload: `{"dod": [{"index", "text", "checked",
        "annotation"}, ...]}`, 1-based `index`, `annotation` either `null` (bare bullet) or an
        object with a `form` key naming the closed-set form
        (`closed-by-phase-commit` | `closed-by-phase-operator` | `closed-by-commit` |
        `resolver-claimed-evaluator-rejected` | `previously-claimed-on-closed-pr`) plus that
        form's own fields (`phase`, `sha`, `date`, `reason`, `pr` as applicable — see
        `_ANNOTATION_FORMS` below for the exact field set per form). No `## Definition of done`
        section in the body is not an error — `ok` with `dod: []` (dod-annotations.md's "Edge
        cases": "Skip projection silently").

        An **unknown annotation** (the trailing `(...)` doesn't start with one of the three
        recognized prefix words) or **two annotations stacked** on one bullet (a second
        annotation-shaped parenthetical immediately precedes the one already peeled off the tail)
        returns `DOD_MALFORMED` (`needs_decision`), never a crash, never a best-effort guess at
        what the author meant.

        `--render`: instead of the `dod` payload, re-emits the **exact parsed bullets** as
        Markdown text under `{"rendered": "...bullet lines, joined by \\n, with a single trailing
        newline..."}` — see the docstring of `render_dod_bullets` for the byte-identical
        round-trip guarantee this mode exists to prove. `--render` still parses first: a malformed
        body still returns `DOD_MALFORMED` under `--render`, it does not silently render a
        best-effort guess.

    parse.py oq-links <body-file>
        Parses the `## Open questions` section (marked by the `<!-- open-question-links:v1 -->`
        first line) per `skills/_shared/open-question-links.md`. `ok` payload: `{"open_questions":
        [{"oq_id", "source", "gates", "disposition", "question", "audience", "default",
        "retires_when"}, ...]}`. `disposition` is one of the closed set of exactly three values
        (`scoped-out` | `in-scope (blocked)` | `provisional-default`); `default`/`retires_when`
        are `null` except on `provisional-default` entries (the only disposition that carries
        them). No `## Open questions` section (or a section without the marker) is not an error
        — `ok` with `open_questions: []` (open-question-links.md's Format section: "Omit the
        whole section when no OQ gates the issue").

    parse.py phases <body-file>
        Parses a plan's `## Phases` section per
        `skills/planner/references/plan-schema.md`'s numbered-list-with-structured-
        keys grammar. `ok` payload: `{"phases": [{"number", "title", "kind", "ships",
        "closes_dod", "deliverable", "depends_on", "sub_issue"}, ...]}`. `kind` is one of the
        closed set of exactly three values (`code-shipping` | `operator` | `decision-only`);
        `closes_dod` is either the literal string `"(none)"` or a list of 1-based ints;
        `depends_on` is either the literal string `"(none)"` or a list of ints (phase numbers);
        `sub_issue` is tri-state — `None` when the optional `sub-issue:` line is absent
        (**unmapped**), the literal string `"(none)"` for an explicit **substrate** claim, or an
        int (the one sub-issue this phase serves). No `## Phases` section is
        `ok` with `phases: []` — a plan legitimately omits `## Phases` for single-phase issues and
        epics (plan-schema.md: "multi-phase issues only — omit for single-phase; epics use the
        dedicated `## Story breakdown` / `## Integration strategy` sections"), so an absent
        section is not itself malformed; only a **present-but-broken** section is.

        A malformed `## Phases` section (a numbered entry missing a required structured key, an
        entry whose `kind:` value is outside the closed set, non-sequential/duplicate phase
        numbers, a `closes-dod`/`depends-on` value that isn't `(none)` and doesn't parse as the
        documented reference-list shape, or a `sub-issue:` value that is neither `(none)` nor
        exactly one `#<N>`) returns `PHASES_MALFORMED`.

Envelope conformance (architecture.md §3) on every output: exactly one JSON object on stdout,
`status` is `ok` or `needs_decision`, `notices: []` always present. Exit 0 on both `ok` and
`needs_decision` (a decision is a valid outcome, not a process failure); exit 2 is reserved for a
genuine usage error (missing/unreadable file, unknown subcommand) — no envelope in that case, per
the exit-code contract every other v2 script also honors.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipelib.decisions import DOD_MALFORMED, PHASES_MALFORMED, needs_decision  # noqa: E402
from pipelib.envelope import (  # noqa: E402
    EXIT_OK,
    EXIT_USAGE_ERROR,
    emit_needs_decision,
    emit_ok,
)

# ============================================================================================
# Shared file-reading helper
# ============================================================================================


def _read_text_or_die(path_str):
    """Read `path_str` as UTF-8 text (architecture.md §1's encoding pin). Exits 2 with a faithful
    stderr message on a missing/unreadable file or a decode failure — a usage error, not a
    `needs_decision` (the caller gave a bad path; there is no operator decision to surface for
    "the file isn't there").
    """
    path = Path(path_str)
    try:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            return fh.read()
    except OSError as exc:
        sys.stderr.write("PARSE_FILE_UNREADABLE: %s: %s\n" % (path_str, exc))
        sys.exit(EXIT_USAGE_ERROR)
    except UnicodeDecodeError as exc:
        sys.stderr.write("PARSE_FILE_NOT_UTF8: %s: %s\n" % (path_str, exc))
        sys.exit(EXIT_USAGE_ERROR)


def _find_section(lines, heading_pattern):
    """Locate a `## <heading>` section (case-insensitive on the heading text, matching
    dod-annotations.md's "Section finder": "case-insensitive on the section title"). Returns
    `(start_index, end_index)` — a 0-based half-open slice `lines[start_index:end_index]` of the
    section's body lines (the heading line itself excluded) — or `None` if no heading matches.
    Reads "subsequent lines until the next `##` heading or EOF", exactly as dod-annotations.md
    specifies (used identically for oq-links' `## Open questions` and phases' `## Phases`, since
    all three shared contracts describe the same section-finder shape).
    """
    heading_re = re.compile(r"^##\s+" + heading_pattern + r"\s*(?:\(.*\))?\s*$", re.IGNORECASE)
    next_heading_re = re.compile(r"^##(?!#)")
    start = None
    for i, line in enumerate(lines):
        if heading_re.match(line):
            start = i + 1
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start, len(lines)):
        if next_heading_re.match(lines[j]):
            end = j
            break
    return start, end


# ============================================================================================
# `dod` subcommand — skills/_shared/dod-annotations.md
# ============================================================================================

# dod-annotations.md's own "Recognition regex (informal)", ported verbatim to Python syntax. Group
# 1: leading whitespace. Group 2: checkbox state char (` `/`x`/`X`). Group 3: bullet text (non-
# greedy up to an optional trailing annotation). Group 4: the annotation's prefix word. Group 5:
# everything after the prefix word, up to the closing paren.
_DOD_BULLET_RE = re.compile(
    r"^( *)-[ ]+\[([ xX])\][ ]+(.+?)(?:[ ]+\((closed by|resolver claimed phase|previously claimed by) (.+)\))?$"
)

# `_DOD_BULLET_RE`'s prefix alternation is intentionally narrow (the exact three closed-set prefix
# words) so a well-formed non-annotation trailing parenthetical in ordinary bullet prose — e.g.
# `- [ ] Support CSV export (stretch goal)` — is correctly left alone as plain text, never flagged.
# But that narrowness means a genuine **near-miss** annotation attempt (a prefix word typo, an
# attribution phrase using the wrong verb) fails to match the alternation at all and gets silently
# absorbed into the bullet's `text` group instead of being recognized as an attempted-but-broken
# annotation. This second regex is the "does this trailing parenthetical look like an annotation
# attempt regardless of its exact prefix wording" heuristic: it fires on the same attribution
# sub-vocabulary the three real forms are built from (`phase <N>`, a 7-char hex commit sha,
# `operator action <date>`, or `evaluator rejected`) — content ordinary free-text bullets don't
# happen to contain — so a plain stretch-goal/scope-note parenthetical never matches this pattern
# and only a genuine mis-worded attribution attempt does.
_ANNOTATION_LOOKALIKE_RE = re.compile(
    r"\((?:[^()]*\bphase \d+\b[^()]*|[^()]*\b[0-9a-f]{7}\b[^()]*|[^()]*\boperator action\b[^()]*"
    r"|[^()]*\bevaluator rejected\b[^()]*)\)\s*$"
)

# A top-level bullet only — dod-annotations.md's "Indexing and parsing rules": "Sub-bullets
# (indented with two or more leading spaces beneath a top-level bullet) are detail, not DoD
# items." A top-level bullet's own leading-whitespace group (captured group 1 above) must
# therefore be empty or a single space — never two or more — for the line to count at all.
_TOP_LEVEL_INDENT_RE = re.compile(r"^ {0,1}$")

# Per-form tail parsers. Each dispatches on the exact prefix word `_DOD_BULLET_RE` captured, then
# further parses that prefix's own tail shape (dod-annotations.md's "Then dispatch on the prefix
# word" list). Every regex is anchored full-match (`fullmatch`) so a tail that merely *starts with*
# the right shape but has trailing garbage is rejected, not silently truncated.
_TAIL_CLOSED_BY_PHASE_RE = re.compile(
    r"^phase (\d+), commit ([0-9a-f]{7})$"
)
_TAIL_CLOSED_BY_PHASE_OPERATOR_RE = re.compile(
    r"^phase (\d+), operator action (\d{4}-\d{2}-\d{2})$"
)
_TAIL_CLOSED_BY_COMMIT_RE = re.compile(r"^commit ([0-9a-f]{7})$")
_TAIL_RESOLVER_REJECTED_RE = re.compile(
    r"^(\d+), commit ([0-9a-f]{7}); evaluator rejected: (.+)$"
)
# The rejection reason itself must contain no literal parenthesis — dod-annotations.md's "Edge
# cases": "the evaluator-rejection reason should sanitize any `(` / `)` to `[` / `]` to keep the
# parser unambiguous." A reason containing a literal `(`/`)` is therefore never a well-formed
# free-text rationale; it is either an unsanitized author mistake or (the adversarial case this
# guards) a **second annotation stacked** inside what the outer bullet regex's greedy tail-capture
# folded into this one's free-text reason field (dod-annotations.md's "never carries two
# annotations stacked" invariant) — either way, `DOD_MALFORMED`, never silently accepted as
# reason text.
_REASON_CONTAINS_PAREN_RE = re.compile(r"[()]")
_TAIL_PREVIOUSLY_CLAIMED_RE = re.compile(
    r"^phase (\d+), commit ([0-9a-f]{7}) on closed PR #(\d+)$"
)

# Which prefix words pair with which tail regex + resulting form name + field extractor. Order
# matters only in that "closed by" fans out to three sub-shapes tried in this order (phase+commit,
# phase+operator-date, bare commit) — the first that fullmatches wins; if none do, it's an unknown
# annotation shape under a recognized prefix word, which is still `DOD_MALFORMED` (a prefix word
# alone does not certify the whole annotation parses).
def _parse_closed_by_tail(tail):
    m = _TAIL_CLOSED_BY_PHASE_RE.fullmatch(tail)
    if m:
        return {
            "form": "closed-by-phase-commit",
            "phase": int(m.group(1)),
            "sha": m.group(2),
        }
    m = _TAIL_CLOSED_BY_PHASE_OPERATOR_RE.fullmatch(tail)
    if m:
        return {
            "form": "closed-by-phase-operator",
            "phase": int(m.group(1)),
            "date": m.group(2),
        }
    m = _TAIL_CLOSED_BY_COMMIT_RE.fullmatch(tail)
    if m:
        return {"form": "closed-by-commit", "sha": m.group(1)}
    return None


def _parse_resolver_claimed_tail(tail):
    m = _TAIL_RESOLVER_REJECTED_RE.fullmatch(tail)
    if not m:
        return None
    reason = m.group(3)
    if _REASON_CONTAINS_PAREN_RE.search(reason):
        return None
    return {
        "form": "resolver-claimed-evaluator-rejected",
        "phase": int(m.group(1)),
        "sha": m.group(2),
        "reason": reason,
    }


def _parse_previously_claimed_tail(tail):
    m = _TAIL_PREVIOUSLY_CLAIMED_RE.fullmatch(tail)
    if not m:
        return None
    return {
        "form": "previously-claimed-on-closed-pr",
        "phase": int(m.group(1)),
        "sha": m.group(2),
        "pr": int(m.group(3)),
    }


_PREFIX_TAIL_PARSERS = {
    "closed by": _parse_closed_by_tail,
    "resolver claimed phase": _parse_resolver_claimed_tail,
    "previously claimed by": _parse_previously_claimed_tail,
}

# Every annotation form's own render template, keyed by `form` — the exact inverse of the tail
# parsers above, used by `--render` to reconstruct the trailing `(...)` byte-for-byte from the
# parsed fields (never from the original raw line, so a render bug can't hide behind an
# accidental pass-through of unparsed text).
_FORM_RENDERERS = {
    "closed-by-phase-commit": lambda a: "closed by phase %d, commit %s" % (a["phase"], a["sha"]),
    "closed-by-phase-operator": lambda a: "closed by phase %d, operator action %s"
    % (a["phase"], a["date"]),
    "closed-by-commit": lambda a: "closed by commit %s" % a["sha"],
    "resolver-claimed-evaluator-rejected": lambda a: (
        "resolver claimed phase %d, commit %s; evaluator rejected: %s"
        % (a["phase"], a["sha"], a["reason"])
    ),
    "previously-claimed-on-closed-pr": lambda a: (
        "previously claimed by phase %d, commit %s on closed PR #%d"
        % (a["phase"], a["sha"], a["pr"])
    ),
}

# Note on detecting two annotations stacked on one bullet (dod-annotations.md's "A bullet never
# carries two annotations stacked" invariant): `_DOD_BULLET_RE`'s `text` group is non-greedy but
# its `tail` group is greedy and anchored to the line's end, so the regex always prefers capturing
# *any* trailing `(closed by|resolver claimed phase|previously claimed by) ...)` suffix as the
# annotation rather than leaving it inside `text` — meaning `text` can never itself retain a
# second, later, closed-set-prefixed annotation to detect. A stacked second annotation instead
# always ends up folded into the *first* annotation's own `tail` capture. Detection therefore
# happens in two other places instead, each matching how that folding actually manifests: (1) the
# `_ANNOTATION_LOOKALIKE_RE` check below, when `prefix_word` came back `None` because the folded
# tail doesn't start with a recognized prefix at all; (2) each tail sub-shape regex is `fullmatch`-
# anchored, so a stacked annotation folded into a *recognized* prefix's tail simply fails to
# fullmatch that prefix's known field shapes (extra trailing content after the expected fields) —
# except `resolver claimed phase`'s free-text `reason` field, which would otherwise swallow a
# stacked annotation as ordinary reason text; `_REASON_CONTAINS_PAREN_RE` (below) closes that gap.


class _DodMalformed(Exception):
    """Internal signal: a DoD bullet's annotation is outside the closed set (unknown prefix word,
    a recognized prefix word whose tail doesn't match any of its sub-shapes, or two annotations
    stacked on one bullet). Carries a human-readable `reason` for the `needs_decision` summary.
    Never escapes this module.
    """

    def __init__(self, reason, line_number, raw_line):
        super().__init__(reason)
        self.reason = reason
        self.line_number = line_number
        self.raw_line = raw_line


# The one heading pattern both DoD entry points feed to `_find_section`. A single constant, not
# two spelled literals: `has_dod_section` (the create-vs-append fact) and `parse_dod_bullets`
# (the bullets) must never disagree on what counts as the section — a one-sided tolerance edit
# would let a caller append a SECOND `## Definition of done` onto a body that already has one.
_DOD_HEADING_PATTERN = r"Definition of done"


def has_dod_section(body_text):
    """Whether the body carries a `## Definition of done` section at all — distinct from
    `parse_dod_bullets` returning `[]`, which conflates "no section" with "a section holding no
    top-level checkbox bullets". A caller that must decide whether to *create* the section (the
    requirements-gatherer's DoD write) keys off this; a caller that only projects onto existing
    bullets never needs the distinction (dod-annotations.md's "Skip projection silently").
    """
    return _find_section(body_text.splitlines(), _DOD_HEADING_PATTERN) is not None


def dod_malformed_decision(exc, **context):
    """Build the `DOD_MALFORMED` needs_decision payload for a `_DodMalformed` raised by
    `parse_dod_bullets` — the single home for the operator-facing repair guidance and the
    decision's context schema, which were previously restated per caller (`run_dod` here, plus
    the DoD-composing preps). `context` carries any caller-specific keys (e.g. `issue=`,
    `body_file=`) merged alongside the exception's own `line_number`/`raw_line`."""
    return needs_decision(
        DOD_MALFORMED,
        summary=exc.reason,
        context={
            "line_number": exc.line_number,
            "raw_line": exc.raw_line,
            **context,
        },
        options=[
            "fix the bullet's annotation by hand to match one of the closed-set forms in "
            "skills/_shared/dod-annotations.md, then re-run"
        ],
    )


def parse_dod_bullets(body_text):
    """Parse the `## Definition of done` section's top-level checkbox bullets. Returns a list of
    `{"index", "text", "checked", "annotation"}` dicts (1-based `index`, `annotation` a dict or
    `None`). Raises `_DodMalformed` on the first unrecognized or stacked annotation found — the
    caller turns that into a `DOD_MALFORMED` needs_decision envelope.

    No `## Definition of done` section: returns `[]` (dod-annotations.md's "Edge cases": "Skip
    projection silently").
    """
    lines = body_text.splitlines()
    section = _find_section(lines, _DOD_HEADING_PATTERN)
    if section is None:
        return []
    start, end = section

    bullets = []
    index = 0
    for line_number in range(start, end):
        raw_line = lines[line_number]
        match = _DOD_BULLET_RE.match(raw_line)
        if not match:
            continue  # not a checkbox-bullet line at all (blank line, prose, etc.) — not our concern
        indent, check_char, text, prefix_word, tail = match.groups()
        if not _TOP_LEVEL_INDENT_RE.match(indent):
            continue  # a sub-bullet (indent >= 2) — detail, not a DoD item (dod-annotations.md)

        index += 1
        checked = check_char in ("x", "X")

        annotation = None
        if prefix_word is None:
            # `_DOD_BULLET_RE`'s prefix alternation didn't match anything, so the whole trailing
            # parenthetical (if any) was absorbed into `text`. Before accepting this as a bare,
            # unannotated bullet, check whether `text` nonetheless ends with an annotation
            # *lookalike* — an attribution attempt using the wrong prefix word (a near-miss, not
            # ordinary bullet prose that happens to end in unrelated parentheses).
            lookalike_match = _ANNOTATION_LOOKALIKE_RE.search(text)
            if lookalike_match:
                raise _DodMalformed(
                    "bullet %d has a trailing parenthetical that looks like an attribution "
                    "annotation attempt but does not use one of the closed-set prefix words "
                    "(closed by / resolver claimed phase / previously claimed by): %r"
                    % (index, lookalike_match.group(0)),
                    line_number + 1,
                    raw_line,
                )
        else:
            # A recognized prefix word matched; parse its own tail sub-shape. A stacked second
            # annotation folded into this tail (see the note above `_ANNOTATION_LOOKALIKE_RE`)
            # surfaces as either a fullmatch failure against every known field shape for this
            # prefix, or — for `resolver claimed phase`'s free-text reason field specifically — a
            # literal paren inside the reason (`_REASON_CONTAINS_PAREN_RE`, checked inside
            # `_parse_resolver_claimed_tail`). Both return `None` here, handled identically below.
            tail_parser = _PREFIX_TAIL_PARSERS[prefix_word]
            annotation = tail_parser(tail)
            if annotation is None:
                raise _DodMalformed(
                    "bullet %d's %r annotation does not match any recognized tail shape: %r"
                    % (index, prefix_word, tail),
                    line_number + 1,
                    raw_line,
                )

        bullets.append(
            {"index": index, "text": text, "checked": checked, "annotation": annotation}
        )
    return bullets


def render_dod_bullets(bullets, indent=""):
    """Re-emit `bullets` (as returned by `parse_dod_bullets`) as Markdown checkbox-bullet lines,
    joined by `\\n` with one trailing `\\n` — the exact inverse of `parse_dod_bullets` given the
    same leading `indent` the bullets were parsed at (an empty string for the always-top-level
    case `parse_dod_bullets` restricts itself to).

    This is the round-trip fidelity guarantee the `dod --render` DoD box exercises: parsing a
    body's DoD section and rendering the result must reproduce the **section's bullet lines**
    byte-for-byte (the test compares this against the original bullet-line text extracted from
    the same fixture, not the whole file — headings/blank-lines/prose around the bullets are not
    part of what `parse_dod_bullets` captures, so they are correctly not part of what this
    reproduces). A lossy parse (a field silently dropped or reformatted) fails this by
    construction, since the render path only ever has the parsed fields to work from — it never
    holds onto or falls back to the original raw line.
    """
    out = []
    for bullet in bullets:
        check_char = "x" if bullet["checked"] else " "
        line = "%s- [%s] %s" % (indent, check_char, bullet["text"])
        annotation = bullet["annotation"]
        if annotation is not None:
            renderer = _FORM_RENDERERS[annotation["form"]]
            line += " (%s)" % renderer(annotation)
        out.append(line)
    return "\n".join(out) + ("\n" if out else "")


def run_dod(args):
    body_text = _read_text_or_die(args.body_file)
    try:
        bullets = parse_dod_bullets(body_text)
    except _DodMalformed as exc:
        emit_needs_decision(dod_malformed_decision(exc, body_file=args.body_file))
        sys.exit(EXIT_OK)

    if args.render:
        emit_ok(payload={"rendered": render_dod_bullets(bullets)})
    else:
        emit_ok(payload={"dod": bullets})
    sys.exit(EXIT_OK)


# ============================================================================================
# `oq-links` subcommand — skills/_shared/open-question-links.md
# ============================================================================================

_OQ_LINKS_MARKER = "<!-- open-question-links:v1 -->"

# The closed disposition set (open-question-links.md §Dispositions) — exactly three values, never
# extended ad hoc.
_OQ_DISPOSITIONS = frozenset({"scoped-out", "in-scope (blocked)", "provisional-default"})

# One OQ entry starts with a `- OQ: ...` line and may continue on subsequent lines that begin
# (after their own leading whitespace) with an em dash `—` — open-question-links.md's worked
# example: continuation lines are `  — disposition: ... — question: ...` etc., soft-wrapped
# beneath the `- OQ:` line they belong to. `—` is the literal em dash (not a hyphen) the
# shared contract itself uses as its field separator throughout the schema block.
_OQ_ENTRY_START_RE = re.compile(r"^- OQ: `([^`]+)` \(([^)]+)\) — gates: (.+)$")
_OQ_CONTINUATION_RE = re.compile(r"^\s+— ")

# Field-extraction regexes, applied to the *joined* (single-line) form of one entry's continuation
# text (see `_join_entry_lines`). Each is independent of the others' presence/absence/order in the
# source, since the schema's own field order is fixed by the template
# (disposition, question, audience, [default, retires-when]) but this parser does not assume a
# reader relies on that fixed order surviving a hand-edit.
# `(?=\s|$)` rather than `\b` for the field terminator: `\b` requires a word/non-word transition,
# which never occurs after a value ending in `)` (a non-word char) followed by a space (also
# non-word) — exactly the shape of `in-scope (blocked)` and `(not filed)`, both real closed-set
# values. A lookahead for "whitespace or end of string" is what "the field's value ends here" is
# actually supposed to mean.
_OQ_DISPOSITION_FIELD_RE = re.compile(
    r"— disposition: (scoped-out|in-scope \(blocked\)|provisional-default)(?=\s|$)"
)
_OQ_QUESTION_FIELD_RE = re.compile(r"— question: (#\d+|\(not filed\))(?=\s|$)")
_OQ_AUDIENCE_FIELD_RE = re.compile(r"— audience: ([^—]+?)(?:\s*—|\s*$)")
_OQ_DEFAULT_FIELD_RE = re.compile(r"— default: ([^—]+?)(?:\s*—|\s*$)")
_OQ_RETIRES_WHEN_FIELD_RE = re.compile(r"— retires-when: ([^—]+?)\s*$")


class _OqLinksMalformed(Exception):
    """Internal signal: an `## Open questions` entry doesn't conform to the closed-set schema
    (unrecognized disposition, a `provisional-default` entry missing its required `default:`/
    `retires-when:` fields, or a `- OQ:` line whose required leading fields don't parse). Distinct
    from `DOD_MALFORMED`/`PHASES_MALFORMED` — the shared contract does not name a dedicated
    decision code for this grammar (open-question-links.md predates architecture.md §3's code
    registry finalization; only `dod`/`phases` are named there), so this raises `AMBIGUOUS` (the
    §3 closed set's residual-ambiguity code), never invents an unregistered new code.
    """

    def __init__(self, reason, line_number, raw_line):
        super().__init__(reason)
        self.reason = reason
        self.line_number = line_number
        self.raw_line = raw_line


def _split_oq_entries(section_lines):
    """Group `section_lines` (already past the `<!-- open-question-links:v1 -->` marker line)
    into one raw-line-list per `- OQ:`-started entry, folding each entry's continuation lines in.
    Non-bullet lines (blank lines between entries, stray prose) are skipped rather than treated as
    a parse error — the marker's presence is what makes this section machine-readable at all; the
    entries within it are the only structured content.
    """
    entries = []
    current = None
    for raw_line in section_lines:
        if _OQ_ENTRY_START_RE.match(raw_line):
            if current is not None:
                entries.append(current)
            current = [raw_line]
        elif current is not None and _OQ_CONTINUATION_RE.match(raw_line):
            current.append(raw_line)
        elif raw_line.strip() == "":
            continue
        else:
            # A non-blank line that is neither a new entry nor a continuation of the current one —
            # if an entry is open, treat it as the end of that entry's continuation run (stray
            # prose after the block); the entry itself is still parsed from what was accumulated.
            if current is not None:
                entries.append(current)
                current = None
    if current is not None:
        entries.append(current)
    return entries


def _parse_one_oq_entry(entry_lines, entry_line_number):
    """Parse one entry's raw lines (the `- OQ:` line plus its continuation lines) into the
    `{"oq_id", "source", "gates", "disposition", "question", "audience", "default",
    "retires_when"}` dict. Raises `_OqLinksMalformed` when a required field is absent or a value
    falls outside its closed set.
    """
    head_match = _OQ_ENTRY_START_RE.match(entry_lines[0])
    if not head_match:  # pragma: no cover — caller only invokes this on lines that already matched
        raise _OqLinksMalformed(
            "entry does not start with the required '- OQ: `<id>` (<source>) — gates: ...' shape",
            entry_line_number,
            entry_lines[0],
        )
    oq_id, source, gates = head_match.groups()

    # The continuation lines carry the rest of the fields, soft-wrapped; joining them with a
    # single space lets the field regexes above match regardless of exactly which physical line a
    # field landed on (open-question-links.md's schema does not pin field-to-line assignment,
    # only field order within the logical entry).
    joined_tail = " ".join(line.strip() for line in entry_lines[1:])
    full_entry_text = entry_lines[0] + (" " + joined_tail if joined_tail else "")

    disposition_match = _OQ_DISPOSITION_FIELD_RE.search(full_entry_text)
    if not disposition_match:
        raise _OqLinksMalformed(
            "OQ `%s` entry is missing a recognized 'disposition:' field (must be one of %s)"
            % (oq_id, sorted(_OQ_DISPOSITIONS)),
            entry_line_number,
            entry_lines[0],
        )
    disposition = disposition_match.group(1)

    question_match = _OQ_QUESTION_FIELD_RE.search(full_entry_text)
    if not question_match:
        raise _OqLinksMalformed(
            "OQ `%s` entry is missing a recognized 'question:' field (must be '#<N>' or "
            "'(not filed)')" % oq_id,
            entry_line_number,
            entry_lines[0],
        )
    question = question_match.group(1)

    audience_match = _OQ_AUDIENCE_FIELD_RE.search(full_entry_text)
    audience = audience_match.group(1).strip() if audience_match else None
    if audience is None:
        raise _OqLinksMalformed(
            "OQ `%s` entry is missing the required 'audience:' field" % oq_id,
            entry_line_number,
            entry_lines[0],
        )

    default_match = _OQ_DEFAULT_FIELD_RE.search(full_entry_text)
    retires_when_match = _OQ_RETIRES_WHEN_FIELD_RE.search(full_entry_text)
    default_value = default_match.group(1).strip() if default_match else None
    retires_when_value = retires_when_match.group(1).strip() if retires_when_match else None

    if disposition == "provisional-default":
        # open-question-links.md §Dispositions: provisional-default "entry MUST carry `default:`
        # ... and `retires-when:`" — required, not optional, for exactly this one disposition.
        if default_value is None or retires_when_value is None:
            raise _OqLinksMalformed(
                "OQ `%s` has disposition 'provisional-default' but is missing 'default:' and/or "
                "'retires-when:' (both are required for this disposition)" % oq_id,
                entry_line_number,
                entry_lines[0],
            )
    else:
        # Present on a non-provisional-default entry would be a hand-edit error the shared
        # contract doesn't sanction (those two fields are documented as "[provisional-default
        # only]") — refuse rather than silently accept a field that shouldn't be there.
        if default_value is not None or retires_when_value is not None:
            raise _OqLinksMalformed(
                "OQ `%s` has disposition '%s' but carries 'default:'/'retires-when:' fields, "
                "which are provisional-default-only" % (oq_id, disposition),
                entry_line_number,
                entry_lines[0],
            )

    return {
        "oq_id": oq_id,
        "source": source,
        "gates": gates,
        "disposition": disposition,
        "question": question,
        "audience": audience,
        "default": default_value,
        "retires_when": retires_when_value,
    }


def parse_oq_links(body_text):
    """Parse the `## Open questions` section's `<!-- open-question-links:v1 -->` entries. Returns
    a list of per-entry dicts (see `_parse_one_oq_entry`). Raises `_OqLinksMalformed` on the first
    entry that doesn't conform.

    No `## Open questions` section, or a section present without the `<!-- open-question-links:v1
    -->` marker as its first line: returns `[]` — open-question-links.md's Format section: "Omit
    the whole section when no OQ gates the issue," and readers "locate the registry with a
    `startswith` match on that line," so a section lacking the marker is not this registry at all
    (it's not this parser's job to guess at an unmarked section's meaning).
    """
    lines = body_text.splitlines()
    section = _find_section(lines, r"Open questions")
    if section is None:
        return []
    start, end = section
    section_lines = lines[start:end]

    # Skip leading blank lines before checking for the marker — a body author may leave one blank
    # line between the heading and the marker; the marker still must be the section's first
    # non-blank content to count as "present" (mirrors the marker-comment convention used
    # elsewhere in this repo, where the marker is the first line of *content*, not necessarily the
    # literal first line of a comment that might carry leading whitespace).
    first_content_index = None
    for i, line in enumerate(section_lines):
        if line.strip() != "":
            first_content_index = i
            break
    if first_content_index is None or section_lines[first_content_index].strip() != _OQ_LINKS_MARKER:
        return []

    entries_lines = _split_oq_entries(section_lines[first_content_index + 1 :])
    results = []
    for entry_lines in entries_lines:
        entry_line_number = start + first_content_index + 1  # approximate, refined below
        # Recompute the precise 1-based source line number of this entry's head line for the
        # decision context (best-effort line attribution for the operator, not load-bearing for
        # correctness — the parsed fields are what matters).
        try:
            entry_line_number = lines.index(entry_lines[0], start) + 1
        except ValueError:  # pragma: no cover — entry_lines[0] always came from `lines` itself
            pass
        results.append(_parse_one_oq_entry(entry_lines, entry_line_number))
    return results


def run_oq_links(args):
    body_text = _read_text_or_die(args.body_file)
    try:
        entries = parse_oq_links(body_text)
    except _OqLinksMalformed as exc:
        from pipelib.decisions import AMBIGUOUS  # local import: keep the module-level import list

        # focused on the two decision codes this file canonically emits (DOD_MALFORMED,
        # PHASES_MALFORMED per architecture.md §3); AMBIGUOUS is pipelib's general residual code,
        # used here only on this one non-canonical-emitter path.
        decision = needs_decision(
            AMBIGUOUS,
            summary=exc.reason,
            context={
                "body_file": args.body_file,
                "line_number": exc.line_number,
                "raw_line": exc.raw_line,
            },
            options=[
                "fix the entry by hand to match the schema in "
                "skills/_shared/open-question-links.md, then re-run"
            ],
        )
        emit_needs_decision(decision)
        sys.exit(EXIT_OK)

    emit_ok(payload={"open_questions": entries})
    sys.exit(EXIT_OK)


# ============================================================================================
# `phases` subcommand — skills/planner/references/plan-schema.md `## Phases`
# ============================================================================================

# The closed `kind:` set (plan-schema.md: "kind: code-shipping | operator | decision-only").
_PHASE_KINDS = frozenset({"code-shipping", "operator", "decision-only"})

# `N. **Phase N — <title>**` — plan-schema.md's worked template line 1 of each numbered entry. The
# two `N`s (the list ordinal and the "Phase N" label) are captured separately so a mismatch
# between them (a renumbering slip) is a detectable malformation rather than silently trusting
# whichever one happens to be read.
_PHASE_HEAD_RE = re.compile(r"^(\d+)\.\s+\*\*Phase (\d+)\s*—\s*(.+?)\*\*\s*$")

# Structured key lines beneath a phase head, each `   - key: value` (plan-schema.md's template
# indents these one level under the numbered head). `re.DOTALL` is not used — value is always the
# rest of the line.
_PHASE_KEY_RE = re.compile(
    r"^\s*-\s+(kind|ships|closes-dod|deliverable|depends-on|sub-issue):\s*(.*)$"
)

# `sub-issue` is deliberately absent: it is recognized-but-**not-required**, which is the whole
# backward-compatibility mechanism. This grammar is bidirectionally closed (an unrecognized line
# raises, and so does a missing required key), so making the key required would turn every plan
# authored before it existed into `PHASES_MALFORMED` — and the planner's revise mode, the one path
# that could repair such a plan, parses exactly those bodies.
_REQUIRED_PHASE_KEYS = frozenset({"kind", "ships", "closes-dod", "deliverable", "depends-on"})

# `closes-dod`/`depends-on` values: either the literal `(none)` or a comma-separated reference
# list. `closes-dod` references are bare 1-based ints (dod-annotations.md's indexing: "The first
# top-level bullet is index 1"); `depends-on` references are bare ints (earlier phase numbers,
# plan-schema.md: "depends-on: <earlier phase numbers, or `(none)` for the head phase>").
_REF_LIST_ITEM_RE = re.compile(r"^\d+$")

# `sub-issue:` values: either the literal `(none)` or exactly ONE `#<N>` issue reference. The `#`
# is required because everywhere else in plan-schema.md an *issue* is written `#<N>` while a bare
# int means a DoD index or a phase number — one spelling per meaning keeps `sub-issue: 3` from
# reading as "phase 3". Single-valued by contract: the phase→sub-issue map is N:1 (several phases
# may serve one sub-issue; a phase serves at most one), so a comma-separated list is malformed
# rather than a shorthand to be silently narrowed.
_PHASE_SUB_ISSUE_RE = re.compile(r"^#(\d+)$")


class _PhasesMalformed(Exception):
    """Internal signal: the `## Phases` section is present but does not parse — a phase entry
    missing a required key, a `kind:` value outside the closed set, non-sequential/duplicate phase
    numbers, a `closes-dod`/`depends-on` value that is neither `(none)` nor a well-formed
    reference list, a `sub-issue:` value that is neither `(none)` nor a single `#<N>`, or a
    numbered head whose ordinal and "Phase N" label disagree. Never escapes this module.
    """

    def __init__(self, reason, line_number, raw_line):
        super().__init__(reason)
        self.reason = reason
        self.line_number = line_number
        self.raw_line = raw_line


def _parse_ref_list_field(value, field_name, phase_number, line_number, raw_line):
    """Parse a `closes-dod`/`depends-on` field value: either the literal `(none)` (returned
    verbatim as the string, per this module's documented `"(none)"`-or-list-of-ints payload
    shape) or a comma-separated list of bare non-negative ints. Raises `_PhasesMalformed` on
    anything else (empty value, non-numeric item, stray punctuation).
    """
    value = value.strip()
    if value == "(none)":
        return "(none)"
    if value == "":
        raise _PhasesMalformed(
            "phase %d's '%s:' field is empty (must be '(none)' or a comma-separated list of "
            "numbers)" % (phase_number, field_name),
            line_number,
            raw_line,
        )
    items = [item.strip() for item in value.split(",")]
    parsed = []
    for item in items:
        if not _REF_LIST_ITEM_RE.match(item):
            raise _PhasesMalformed(
                "phase %d's '%s:' field has a non-numeric reference %r (must be '(none)' or a "
                "comma-separated list of numbers)" % (phase_number, field_name, item),
                line_number,
                raw_line,
            )
        parsed.append(int(item))
    return parsed


def _parse_sub_issue_field(value, phase_number, line_number, raw_line):
    """Parse a `sub-issue:` field value: either the literal `(none)` (returned verbatim as the
    string, matching `_parse_ref_list_field`'s payload convention — an explicit *substrate* claim,
    groundwork no single sub-issue can demonstrate) or a single `#<N>` reference returned as an
    int. Raises `_PhasesMalformed` on an empty value, a bare int, a comma-separated list, `#0`, or
    any other shape.
    """
    value = value.strip()
    if value == "(none)":
        return "(none)"
    match = _PHASE_SUB_ISSUE_RE.match(value)
    if match is None:
        raise _PhasesMalformed(
            "phase %d's 'sub-issue:' field is %r (must be '(none)' or exactly one '#<N>' "
            "sub-issue reference — the phase-to-sub-issue map is N:1, so a list is not legal)"
            % (phase_number, value),
            line_number,
            raw_line,
        )
    number = int(match.group(1))
    if number < 1:
        raise _PhasesMalformed(
            "phase %d's 'sub-issue:' field references '#%d' (issue numbers start at 1)"
            % (phase_number, number),
            line_number,
            raw_line,
        )
    return number


def parse_phases(body_text):
    """Parse the `## Phases` section into a list of `{"number", "title", "kind", "ships",
    "closes_dod", "deliverable", "depends_on", "sub_issue"}` dicts, in the order they appear in
    the section (plan-schema.md's numbered list is itself the intended sequencing, mirrored here as
    list order — no independent sort is applied). Raises `_PhasesMalformed` on any parse failure.

    `sub_issue` is tri-state, and the three values are distinguishable on purpose — the planner's
    plan-versus-live diff and reviewer Dimension 7 both read them:

      * `None`     — the `sub-issue:` line is absent: **unmapped** (a plan authored before the key
                     existed, or a mapping never made). An absent key is NOT `(none)`.
      * `"(none)"` — `sub-issue: (none)`: **substrate**, explicitly claimed.
      * `int`      — `sub-issue: #214`: this phase serves that sub-issue.

    No `## Phases` section: returns `[]` — this is a legitimate shape (single-phase issues and
    epics omit it entirely, plan-schema.md), never `PHASES_MALFORMED` on its own; only a
    **present-but-broken** section raises.
    """
    lines = body_text.splitlines()
    section = _find_section(lines, r"Phases")
    if section is None:
        return []
    start, end = section

    # Group each phase head line with the structured-key lines that follow it, up to the next
    # phase head or the section end.
    head_indices = [i for i in range(start, end) if _PHASE_HEAD_RE.match(lines[i])]
    if not head_indices:
        # A `## Phases` heading with no parseable numbered entry beneath it at all is itself
        # malformed — an empty section would have been omitted entirely per the schema's own
        # "omit for single-phase" rule, so a *present* heading implies at least one entry is
        # expected.
        raise _PhasesMalformed(
            "'## Phases' section is present but contains no parseable numbered phase entry",
            start + 1,
            lines[start] if start < len(lines) else "",
        )

    phases = []
    seen_numbers = []
    for idx, head_index in enumerate(head_indices):
        head_match = _PHASE_HEAD_RE.match(lines[head_index])
        ordinal, label_number, title = head_match.groups()
        if ordinal != label_number:
            raise _PhasesMalformed(
                "phase entry's list ordinal (%s) does not match its 'Phase %s' label"
                % (ordinal, label_number),
                head_index + 1,
                lines[head_index],
            )
        phase_number = int(ordinal)

        body_end = head_indices[idx + 1] if idx + 1 < len(head_indices) else end
        found_keys = {}
        for line_index in range(head_index + 1, body_end):
            raw_line = lines[line_index]
            if raw_line.strip() == "":
                continue
            key_match = _PHASE_KEY_RE.match(raw_line)
            if not key_match:
                raise _PhasesMalformed(
                    "phase %d has an unrecognized line where a structured '- key: value' entry "
                    "was expected: %r" % (phase_number, raw_line),
                    line_index + 1,
                    raw_line,
                )
            key, value = key_match.groups()
            if key in found_keys:
                raise _PhasesMalformed(
                    "phase %d's '%s:' key is given more than once" % (phase_number, key),
                    line_index + 1,
                    raw_line,
                )
            found_keys[key] = (value.strip(), line_index + 1, raw_line)

        missing = _REQUIRED_PHASE_KEYS - found_keys.keys()
        if missing:
            raise _PhasesMalformed(
                "phase %d is missing required key(s): %s" % (phase_number, ", ".join(sorted(missing))),
                head_index + 1,
                lines[head_index],
            )

        kind_value, kind_line, kind_raw = found_keys["kind"]
        if kind_value not in _PHASE_KINDS:
            raise _PhasesMalformed(
                "phase %d's 'kind:' value %r is not one of the closed set %s"
                % (phase_number, kind_value, sorted(_PHASE_KINDS)),
                kind_line,
                kind_raw,
            )

        ships_value, _, _ = found_keys["ships"]
        if ships_value == "":
            raise _PhasesMalformed(
                "phase %d's 'ships:' field is empty" % phase_number,
                found_keys["ships"][1],
                found_keys["ships"][2],
            )

        deliverable_value, _, _ = found_keys["deliverable"]
        if deliverable_value == "":
            raise _PhasesMalformed(
                "phase %d's 'deliverable:' field is empty" % phase_number,
                found_keys["deliverable"][1],
                found_keys["deliverable"][2],
            )

        closes_dod_raw, closes_dod_line, closes_dod_line_text = found_keys["closes-dod"]
        closes_dod = _parse_ref_list_field(
            closes_dod_raw, "closes-dod", phase_number, closes_dod_line, closes_dod_line_text
        )

        depends_on_raw, depends_on_line, depends_on_line_text = found_keys["depends-on"]
        depends_on = _parse_ref_list_field(
            depends_on_raw, "depends-on", phase_number, depends_on_line, depends_on_line_text
        )

        sub_issue = None
        if "sub-issue" in found_keys:
            sub_issue_raw, sub_issue_line, sub_issue_line_text = found_keys["sub-issue"]
            sub_issue = _parse_sub_issue_field(
                sub_issue_raw, phase_number, sub_issue_line, sub_issue_line_text
            )

        if phase_number in seen_numbers:
            raise _PhasesMalformed(
                "phase number %d is used more than once" % phase_number,
                head_index + 1,
                lines[head_index],
            )
        if seen_numbers and phase_number != seen_numbers[-1] + 1:
            raise _PhasesMalformed(
                "phase numbers are not sequential: phase %d follows phase %d"
                % (phase_number, seen_numbers[-1]),
                head_index + 1,
                lines[head_index],
            )
        seen_numbers.append(phase_number)

        phases.append(
            {
                "number": phase_number,
                "title": title.strip(),
                "kind": kind_value,
                "ships": ships_value,
                "closes_dod": closes_dod,
                "deliverable": deliverable_value,
                "depends_on": depends_on,
                # Always present, `None` when the line is absent, so the dict's key set stays
                # stable across the pre- and post-contract grammars.
                "sub_issue": sub_issue,
            }
        )

    return phases


def run_phases(args):
    body_text = _read_text_or_die(args.body_file)
    try:
        phases = parse_phases(body_text)
    except _PhasesMalformed as exc:
        decision = needs_decision(
            PHASES_MALFORMED,
            summary=exc.reason,
            context={
                "body_file": args.body_file,
                "line_number": exc.line_number,
                "raw_line": exc.raw_line,
            },
            options=[
                "fix the '## Phases' section by hand to match the structured-key grammar in "
                "skills/planner/references/plan-schema.md, then re-run"
            ],
        )
        emit_needs_decision(decision)
        sys.exit(EXIT_OK)

    emit_ok(payload={"phases": phases})
    sys.exit(EXIT_OK)


# ============================================================================================
# Dispatch
# ============================================================================================


def build_parser():
    parser = argparse.ArgumentParser(
        prog="parse.py",
        description="One parser for the shared GitHub body grammars (architecture.md §2, §3).",
    )
    sub = parser.add_subparsers(dest="subcommand")

    p_dod = sub.add_parser("dod")
    p_dod.add_argument("body_file")
    p_dod.add_argument("--render", action="store_true")

    p_oq = sub.add_parser("oq-links")
    p_oq.add_argument("body_file")

    p_phases = sub.add_parser("phases")
    p_phases.add_argument("body_file")

    return parser


def main(argv):
    parser = build_parser()
    if not argv:
        parser.print_usage(sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)
    args = parser.parse_args(argv)
    if args.subcommand is None:
        parser.print_usage(sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)

    if args.subcommand == "dod":
        run_dod(args)
    elif args.subcommand == "oq-links":
        run_oq_links(args)
    elif args.subcommand == "phases":
        run_phases(args)
    else:  # pragma: no cover — argparse's own subparser choices already exclude this
        parser.print_usage(sys.stderr)
        sys.exit(EXIT_USAGE_ERROR)


if __name__ == "__main__":
    main(sys.argv[1:])
