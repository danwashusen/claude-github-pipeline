"""Envelope-conformance assertion helpers (architecture.md §3), importable by every later test
suite that exercises a script emitting an envelope.

These are **test-only** — they live under ``tests/support/`` rather than ``scripts/pipelib/``
per ``tests/README.md``'s S3 note ("envelope-conformance assertion helpers land under
`tests/support/`, NOT in `scripts/pipelib/`") precisely because they call ``unittest``-style
assertion functions (raising ``AssertionError`` with a message on failure), which is a test
concern, not a shared runtime primitive — ``pipelib`` (architecture.md §2) holds the emit/build
side only.

Every helper takes a plain envelope ``dict`` (as produced by ``json.loads`` on a script's stdout,
or by :func:`pipelib.envelope.build_ok` / ``build_needs_decision`` directly) and an optional
``msg`` prefix, and raises ``AssertionError`` on the first conformance violation found — mirroring
plain ``assert`` semantics so these compose naturally inside a ``unittest.TestCase`` method (a
raised ``AssertionError`` fails the test the same way ``self.assertX`` would) without requiring a
``TestCase`` instance to call them on.

Import as: ``from tests.support import envelope_asserts``.
"""

from pipelib.decisions import DECISION_CODES
from pipelib.envelope import EXIT_OK, EXIT_USAGE_ERROR, STATUS_NEEDS_DECISION, STATUS_OK


def _fail(msg, detail):
    full = "%s: %s" % (msg, detail) if msg else detail
    raise AssertionError(full)


def assert_valid_status(envelope, msg=""):
    """``envelope["status"]`` is present and is one of the two closed values (``"ok"`` /
    ``"needs_decision"``) — never any other string, never absent.
    """
    if not isinstance(envelope, dict):
        _fail(msg, "envelope must be a dict, got %s" % type(envelope).__name__)
    status = envelope.get("status")
    if status not in (STATUS_OK, STATUS_NEEDS_DECISION):
        _fail(
            msg,
            "envelope['status'] must be one of %r, got %r"
            % ([STATUS_OK, STATUS_NEEDS_DECISION], status),
        )


def assert_decision_payload_shape(envelope, msg=""):
    """When ``status == "needs_decision"``, ``envelope["decision"]`` exists and has exactly the
    architecture.md §3 shape: ``code`` in the closed decision-code set, and ``summary``,
    ``context``, ``options`` all present (``summary`` a non-empty string, ``context`` a dict,
    ``options`` a list). A no-op (does not raise) when ``status != "needs_decision"`` — this
    assertion is specifically about the decision payload's shape, not about which status the
    envelope carries (use :func:`assert_valid_status` for that).
    """
    assert_valid_status(envelope, msg=msg)
    if envelope.get("status") != STATUS_NEEDS_DECISION:
        return
    decision = envelope.get("decision")
    if not isinstance(decision, dict):
        _fail(msg, "envelope['decision'] must be a dict when status is needs_decision, got %r" % (decision,))
    code = decision.get("code")
    if code not in DECISION_CODES:
        _fail(
            msg,
            "decision['code'] %r is not in the closed decision-code set %r"
            % (code, sorted(DECISION_CODES)),
        )
    summary = decision.get("summary")
    if not isinstance(summary, str) or not summary:
        _fail(msg, "decision['summary'] must be a non-empty string, got %r" % (summary,))
    if "context" not in decision or not isinstance(decision["context"], dict):
        _fail(msg, "decision['context'] must be present and a dict, got %r" % (decision.get("context"),))
    if "options" not in decision or not isinstance(decision["options"], list):
        _fail(msg, "decision['options'] must be present and a list, got %r" % (decision.get("options"),))


def assert_spill_sections_well_formed(envelope, section_names, msg=""):
    """For every name in ``section_names`` (e.g. ``["issue_body", "thread"]``), the envelope's
    ``<name>_mode`` is exactly ``"inline"`` or ``"path"``; ``<name>_bytes`` is a present
    non-negative int; ``<name>_path`` is present **iff** mode is ``"path"`` (never present in
    inline mode, always present and a non-empty string in path mode) — the "*_mode/*_path pairing"
    conformance rule (architecture.md §3, this step's DoD). Also requires the bare ``<name>``
    field to be present (and a str) when mode is ``"inline"``, matching architecture.md §4:
    "Inline-mode sections carry the content in the bare field alongside `*_bytes`."
    """
    for name in section_names:
        mode_key, bytes_key, path_key = "%s_mode" % name, "%s_bytes" % name, "%s_path" % name
        mode = envelope.get(mode_key)
        if mode not in ("inline", "path"):
            _fail(msg, "envelope[%r] must be 'inline' or 'path', got %r" % (mode_key, mode))
        size = envelope.get(bytes_key)
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            _fail(msg, "envelope[%r] must be a non-negative int, got %r" % (bytes_key, size))
        has_path = path_key in envelope
        if mode == "path":
            if not has_path or not isinstance(envelope[path_key], str) or not envelope[path_key]:
                _fail(
                    msg,
                    "envelope[%r] must be present as a non-empty string when %s=='path'"
                    % (path_key, mode_key),
                )
            if name in envelope:
                _fail(
                    msg,
                    "envelope[%r] (bare field) must be absent when %s=='path', got a value"
                    % (name, mode_key),
                )
        else:  # inline
            if has_path:
                _fail(
                    msg,
                    "envelope[%r] must be absent when %s=='inline', but it is present"
                    % (path_key, mode_key),
                )
            if name not in envelope or not isinstance(envelope[name], str):
                _fail(
                    msg,
                    "envelope[%r] (bare field) must be present as a str when %s=='inline'"
                    % (name, mode_key),
                )


def assert_exit_code_contract(returncode, envelope_present, msg=""):
    """The exit-code contract itself (architecture.md §3): exit 0 iff an envelope is present on
    stdout; exit 2 means usage error and **no** envelope; any other non-zero is a hard failure and
    an envelope is not guaranteed (so this assertion does not constrain the ``envelope_present``
    value for that branch — only that 0 and 2 have exactly one valid pairing each).

    ``returncode`` is the process's actual exit code; ``envelope_present`` is a ``bool`` — whether
    the caller successfully parsed exactly one JSON envelope from stdout.
    """
    if returncode == EXIT_OK and not envelope_present:
        _fail(msg, "exit code 0 requires an envelope on stdout, but none was found/parsed")
    if returncode == EXIT_USAGE_ERROR and envelope_present:
        _fail(msg, "exit code 2 (usage error) must not emit an envelope, but one was found")


def assert_write_receipt_shape(envelope, msg=""):
    """A body-bearing write's receipt fields are present and well-typed: ``body_bytes`` a
    non-negative int, ``body_sha256`` a 64-character lowercase hex string (architecture.md §3:
    "Body-bearing writes return `body_bytes` + `body_sha256`").
    """
    body_bytes = envelope.get("body_bytes")
    if not isinstance(body_bytes, int) or isinstance(body_bytes, bool) or body_bytes < 0:
        _fail(msg, "envelope['body_bytes'] must be a non-negative int, got %r" % (body_bytes,))
    body_sha256 = envelope.get("body_sha256")
    if (
        not isinstance(body_sha256, str)
        or len(body_sha256) != 64
        or body_sha256 != body_sha256.lower()
        or any(c not in "0123456789abcdef" for c in body_sha256)
    ):
        _fail(
            msg,
            "envelope['body_sha256'] must be a 64-char lowercase hex string, got %r"
            % (body_sha256,),
        )


def assert_notices_shape(envelope, msg=""):
    """``envelope["notices"]`` is present and is a list (architecture.md §3: "`notices: []`
    ... rides in `notices: []`" — the key is never omitted, even when empty).
    """
    notices = envelope.get("notices")
    if not isinstance(notices, list):
        _fail(msg, "envelope['notices'] must be present and a list, got %r" % (notices,))


def assert_full_envelope_conformance(envelope, spill_section_names=(), msg=""):
    """Convenience: run every shape assertion applicable regardless of a specific script's
    schema — :func:`assert_valid_status`, :func:`assert_decision_payload_shape`,
    :func:`assert_notices_shape`, and (if ``spill_section_names`` given)
    :func:`assert_spill_sections_well_formed`. Does not check write-receipt shape (not every
    envelope is a write) — call :func:`assert_write_receipt_shape` separately when relevant.
    """
    assert_valid_status(envelope, msg=msg)
    assert_decision_payload_shape(envelope, msg=msg)
    assert_notices_shape(envelope, msg=msg)
    if spill_section_names:
        assert_spill_sections_well_formed(envelope, spill_section_names, msg=msg)


__all__ = [
    "assert_valid_status",
    "assert_decision_payload_shape",
    "assert_spill_sections_well_formed",
    "assert_exit_code_contract",
    "assert_write_receipt_shape",
    "assert_notices_shape",
    "assert_full_envelope_conformance",
]
