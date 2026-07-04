#!/usr/bin/env python3
"""Toy end-to-end fixture/example script for pipelib's envelope primitives — NOT a pipeline
script (no `SKILL.md` invokes this; it exists purely so ``tests/test_pipelib.py`` can prove the
whole path — argv in, real subprocess, envelope out — works end to end, and that the
`tests/support/envelope_asserts.py` conformance helpers are importable and correctly validate a
real emitted envelope).

The name is deliberately verbose/prefixed (``pipelib_envelope_fixture_demo``, not e.g.
``demo.py`` or something that could be mistaken for a prep/executor script) so it reads as a test
fixture at a glance, per the S3 brief: "name it so it reads as a fixture/example, not a pipeline
script."

Usage (three scenarios, one per ``--mode``):

    pipelib_envelope_fixture_demo.py --mode ok --scratch <dir>
        Emits an "ok" envelope with one spilled section (forced to path mode regardless of size,
        so the test doesn't need to manufacture 25KB+ of text) and one inline section.

    pipelib_envelope_fixture_demo.py --mode needs-decision
        Emits a "needs_decision" envelope with a hand-picked decision code (AMBIGUOUS), proving
        the needs_decision path end to end.

    pipelib_envelope_fixture_demo.py --mode gh-auth-check
        Actually shells out to `gh auth status` via pipelib.process.run (the locked-down runner)
        and, if that call is classified as an authentication failure, emits a "needs_decision"
        envelope with code AUTH_REQUIRED — the real detection path, not a hand-rolled stand-in.
        Under the offline harness this reaches the fixture-replaying shim (never the real `gh`),
        which is what makes the AUTH_REQUIRED fixture case in tests/test_pipelib.py meaningful:
        the shim returns gh's real auth-failure exit code, and this script's own classification
        logic (in pipelib.process, not test-only mock logic) is what turns that into the decision.
        If the `gh auth status` call succeeds (not under the fixture), emits a plain "ok".

Exit code is EXIT_OK (0) for both --mode ok and --mode needs-decision (needs_decision is a valid
outcome, not an error, per architecture.md §3) and for --mode gh-auth-check regardless of which
branch it takes, matching the same rule.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipelib import process  # noqa: E402  (import after sys.path setup, by necessity)
from pipelib.decisions import AMBIGUOUS, AUTH_REQUIRED, needs_decision  # noqa: E402
from pipelib.envelope import EXIT_OK, emit_needs_decision, emit_ok  # noqa: E402
from pipelib.spill import spill_bytes  # noqa: E402


def _run_mode_ok(scratch_dir):
    spilled_fields = spill_bytes(
        b"this is the toy script's spilled section content\n",
        "toy_section",
        scratch_dir,
        force_path=True,
    )
    inline_fields = spill_bytes(b"small inline text", "toy_inline_section", scratch_dir)
    payload = {"toy_field": "hello from the fixture demo"}
    payload.update(spilled_fields)
    payload.update(inline_fields)
    emit_ok(payload=payload)
    return EXIT_OK


def _run_mode_needs_decision():
    decision = needs_decision(
        AMBIGUOUS,
        summary="toy fixture: more than one candidate matched",
        context={"candidates": ["a", "b"]},
        options=["pick a", "pick b"],
    )
    emit_needs_decision(decision)
    return EXIT_OK


def _run_mode_gh_auth_check():
    result = process.run(["gh", "auth", "status"])
    if result.auth_required:
        decision = needs_decision(
            AUTH_REQUIRED,
            summary="gh authentication required",
            context={"stderr": result.stderr, "returncode": result.returncode},
            options=["run: gh auth login"],
        )
        emit_needs_decision(decision)
    else:
        emit_ok(payload={"gh_auth_ok": True})
    return EXIT_OK


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=["ok", "needs-decision", "gh-auth-check"])
    parser.add_argument("--scratch", default=None, help="scratch dir for --mode ok's spilled section")
    args = parser.parse_args(argv)

    if args.mode == "ok":
        if not args.scratch:
            parser.error("--mode ok requires --scratch <dir>")
        return _run_mode_ok(args.scratch)
    if args.mode == "needs-decision":
        return _run_mode_needs_decision()
    return _run_mode_gh_auth_check()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
