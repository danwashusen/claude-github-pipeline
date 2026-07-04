"""The closed decision-code vocabulary (architecture.md §3) and the ``needs_decision`` payload
builder.

Every script and judgment sub-agent in v2 signals an operator-only choice with one of exactly
these 13 codes — contract tokens, exact strings, never paraphrased or extended ad hoc. Adding a
code is a contract change: update architecture.md §3 and this module together, in the same
change, or ``tests/test_pipelib.py``'s drift-check test (which parses the code list back out of
the doc and asserts it equals :data:`DECISION_CODES`) fails.

Meaning + canonical emitter per code (architecture.md §3):

- ``AUTH_REQUIRED`` — `gh` authentication/permission failure; detected by the pipelib subprocess
  runner (:mod:`pipelib.process`), any script.
- ``EMPTY_BODY_FILE`` — body-bearing write given an empty or missing staged file; ``gh_persist.py``.
- ``MARKER_AMBIGUOUS`` — more than one candidate marker comment/block where the contract expects
  one; the gathers + ``config_block.py``.
- ``DOD_MALFORMED`` — a DoD bullet or annotation outside the closed set; ``parse.py dod``.
- ``PHASES_MALFORMED`` — a plan ``## Phases`` section that doesn't parse; ``parse.py phases``.
- ``ROOT_NOT_ON_MAIN`` / ``ROOT_DIRTY`` / ``ROOT_DIVERGED`` — root-freshness failures;
  ``workspace.py``.
- ``BRANCH_IN_USE`` — the branch is checked out in another worktree; ``workspace.py``.
- ``PLAN_MISSING`` — a required plan is absent; prep scripts + the state-distiller.
- ``THREAD_SUPERSEDED_PLAN`` — thread direction supersedes the recorded plan; the state-distiller.
- ``AMBIGUOUS`` — residual non-marker ambiguity (e.g. multiple epic-branch matches); scripts +
  sub-agents.
- ``BLOCKED_ON_USER`` — progress requires operator input beyond a listable option set; sub-agents.
"""

# Contract tokens — exact strings, order matches architecture.md §3's enumeration.
AUTH_REQUIRED = "AUTH_REQUIRED"
EMPTY_BODY_FILE = "EMPTY_BODY_FILE"
MARKER_AMBIGUOUS = "MARKER_AMBIGUOUS"
DOD_MALFORMED = "DOD_MALFORMED"
PHASES_MALFORMED = "PHASES_MALFORMED"
ROOT_NOT_ON_MAIN = "ROOT_NOT_ON_MAIN"
ROOT_DIRTY = "ROOT_DIRTY"
ROOT_DIVERGED = "ROOT_DIVERGED"
BRANCH_IN_USE = "BRANCH_IN_USE"
PLAN_MISSING = "PLAN_MISSING"
THREAD_SUPERSEDED_PLAN = "THREAD_SUPERSEDED_PLAN"
AMBIGUOUS = "AMBIGUOUS"
BLOCKED_ON_USER = "BLOCKED_ON_USER"

# The closed set, as a frozenset for O(1) membership tests. This is the single object the
# drift-check test compares against the doc-parsed set, and the object other pipelib code
# (e.g. the conformance assertions) validates a decision's ``code`` field against.
DECISION_CODES = frozenset(
    {
        AUTH_REQUIRED,
        EMPTY_BODY_FILE,
        MARKER_AMBIGUOUS,
        DOD_MALFORMED,
        PHASES_MALFORMED,
        ROOT_NOT_ON_MAIN,
        ROOT_DIRTY,
        ROOT_DIVERGED,
        BRANCH_IN_USE,
        PLAN_MISSING,
        THREAD_SUPERSEDED_PLAN,
        AMBIGUOUS,
        BLOCKED_ON_USER,
    }
)

# Non-blocking notice codes ride in ``notices: []`` (architecture.md §3) rather than as a
# ``needs_decision`` — they are not part of the closed decision-code set and are not exhaustively
# enumerated here (a script may introduce a new notice without a contract change, since notices
# are informational, not gating). ``DEPS_UNSUPPORTED`` is named because pipelib/tests reference it
# directly (the capability-gated native-dependency degradation).
DEPS_UNSUPPORTED = "DEPS_UNSUPPORTED"


def needs_decision(code, summary, context=None, options=None):
    """Build the ``decision`` payload object for a ``needs_decision`` envelope.

    ``code`` must be one of :data:`DECISION_CODES` — a ``ValueError`` on anything else means an
    invalid code is caught at the point it's constructed, not silently shipped in an envelope.
    ``context`` and ``options`` default to ``{}`` / ``[]`` (never omitted; architecture.md §3's
    decision payload shape always carries all four keys).

    Returns the payload matching architecture.md §3 verbatim:
    ``{"code": "<CODE>", "summary": "…", "context": {…}, "options": ["…"]}`` — the caller (see
    :func:`pipelib.envelope.emit_needs_decision`) wraps this under ``{"status": "needs_decision",
    "decision": ...}``.
    """
    if code not in DECISION_CODES:
        raise ValueError(
            "pipelib.decisions.needs_decision: %r is not in the closed decision-code set %r"
            % (code, sorted(DECISION_CODES))
        )
    if not isinstance(summary, str) or not summary:
        raise ValueError("pipelib.decisions.needs_decision: summary must be a non-empty string")
    return {
        "code": code,
        "summary": summary,
        "context": dict(context) if context is not None else {},
        "options": list(options) if options is not None else [],
    }
