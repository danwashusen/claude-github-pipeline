"""story_set.py — an epic's story set, read through ``skills/_shared/epic-story-hierarchy.md``'s
two-tier read: the native sub-issue relation first, the legacy ``## Stories`` checklist second,
unioned by issue number with native state winning on overlap.

**Why this module exists.** Four preps read an epic's stories — ``prep_planner`` (just-in-time story
planning, ``stories_filed``), ``prep_slicer`` (the resume set it cuts the remainder against),
``prep_evaluator`` (sibling routing on the story and epic-integration routes) and ``prep_coordinator``
(stage derivation). Each carried its own copy of the union until this module, which is the
``delivery_log.py`` / ``oq_tracker.py`` promotion pattern: one literal algorithm serving one shared
contract named by real consumers. What stays in each prep is the projection onto the facts shape
that prep already reports, and its ``stories_source`` empty-case label.

**One known divergence, kept visible rather than settled here.** The contract says ``mixed`` means
**both** tiers are non-empty. The slicer reads "the checklist half" as the entries that contributed
after the native dedup (a checklist wholly covered natively is ``sub-issues`` — its attention line
would otherwise claim those stories have no native relation); the planner as every parsed bullet,
placeholders included; the evaluator and coordinator as every *filed* bullet before the dedup. This
module offers one classifier, :func:`source`, and each caller passes the half it has always passed,
so no prep's output changed in the promotion; collapsing them onto one reading is a one-argument
diff per caller.

Every function is a pure, non-emitting core (architecture.md §2's pure-core pattern, the S8 lock):
never prints, never exits. The one live read — a checklist-only story's state — is the caller's,
injected as ``fetch_state``, so its failure handling (a decision, or the prep's own hard exit) stays
the caller's too. There is no CLI surface (no shebang, no ``main()``): the only callers are prep
scripts, exactly like ``branching.py``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import parse  # noqa: E402

SOURCE_SUB_ISSUES = "sub-issues"
SOURCE_CHECKLIST = "checklist"
SOURCE_MIXED = "mixed"


def _closed(state):
    return (state or "").upper() == "CLOSED"


def read(sub_issues, issue_body, fetch_state=None):
    """The two tiers of an epic's story set, before any caller's projection.

    Returns ``(story_set, decision_or_none)``; ``story_set`` is ``{"native", "checklist",
    "checklist_raw"}``, each a list of ``{"number", "title", "state", "checked", "live_title"}``:

    - ``native`` — one entry per sub-issue node, in panel order (which is delivery order). ``checked``
      mirrors live state, so a checkbox/state mismatch is unrepresentable on this tier.
    - ``checklist`` — the ``## Stories`` bullets the native tier does not already carry, in source
      order. A bullet for an already-native story is a stale duplicate, not a second story. A
      placeholder bullet (``number: None``, a story nobody has filed) is kept: it is a cut's input.
    - ``checklist_raw`` — every parsed bullet, before the dedup (see the module docstring).

    ``fetch_state(number) -> (state_fact, decision)`` supplies a filed checklist-only story's live
    ``state`` and ``title`` (as ``live_title``); without it those stay ``None``. The first decision it
    returns is returned as-is, with no story set.
    """
    native = [
        {
            "number": node.get("number"),
            "title": node.get("title"),
            "state": node.get("state"),
            "checked": _closed(node.get("state")),
            "live_title": node.get("title"),
        }
        for node in sub_issues or []
    ]
    native_numbers = {entry["number"] for entry in native}

    raw = parse.parse_stories_section(issue_body)
    checklist = []
    for entry in raw:
        number = entry["number"]
        if number is not None and number in native_numbers:
            continue
        state = live_title = None
        if number is not None and fetch_state is not None:
            state_fact, decision = fetch_state(number)
            if decision is not None:
                return None, decision
            state, live_title = state_fact["state"], state_fact["title"]
        checklist.append(
            {
                "number": number,
                "title": entry["title"],
                "state": state,
                "checked": entry["checked"],
                "live_title": live_title,
            }
        )
    return {"native": native, "checklist": checklist, "checklist_raw": raw}, None


def source(native, checklist):
    """``stories_source`` for a native half and a checklist half: ``mixed`` when both are non-empty,
    else whichever is, else ``None`` (no stories at all — a caller that labels that case passes its
    own default, e.g. ``source(...) or SOURCE_CHECKLIST``)."""
    if native and checklist:
        return SOURCE_MIXED
    if native:
        return SOURCE_SUB_ISSUES
    if checklist:
        return SOURCE_CHECKLIST
    return None


def filed(entries):
    """The entries naming a filed issue — placeholders dropped."""
    return [entry for entry in entries if entry["number"] is not None]


def closed_view(story_set):
    """The union as ``[{"number", "title", "state", "closed"}]`` over filed stories only — the shape
    the evaluator's and the coordinator's epic facts report. A checklist entry's ``closed`` is its
    checkbox, and its ``state`` whatever :func:`read` was given (``None`` without a fetch)."""
    return [
        {"number": e["number"], "title": e["title"], "state": e["state"], "closed": e["checked"]}
        for e in story_set["native"] + filed(story_set["checklist"])
    ]
