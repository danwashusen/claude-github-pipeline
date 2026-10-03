# Phase continuation — the checkpoint after a non-final phase ships

Read at the spine's "Return to the routed playbook" when a phase has shipped and an unshipped phase
remains (S5.2 pushed it, S6 projected it, S7 filed its follow-ups). It decides whether this session
ships the next phase too or ends with the non-final handoff. This **phase checkpoint** is not
[`follow-up-tracking.md`](follow-up-tracking.md)'s end-of-loop checkpoint: that `file-at-checkpoint`
batch ran at S7, minutes earlier, and is never a reason to pause.

**The rule this file serves:** a continuation is a fresh continue-mode run in everything but the
conversation. Each phase gets its own prep, push, tracker tick, DoD projection, cold read, and loop
comment, seeded from GitHub exactly as a new session's would be — so the evaluator, the tracker, and a
later session cannot tell which phases shared a session.

## 1. Hard stops — no card, the existing handoff

The next phase is the first unticked row of the `## Phase tracker` S6 just wrote whose `depends-on` is
satisfied — never selected by title.

- The next phase is `operator` / `decision-only` → the operator-phase handoff. The resolver cannot run
  it.
- The run is exiting on a re-route, or is a revision run → that run's own handoff; there is nothing to
  chain.

The last code phase never reaches this file: the spine's ready flip and forward handoff own it.

## 2. Pause or continue

Pause when **any** of these holds; otherwise continue:

- the shipped phase's `checkpoint` (`facts.phases`) is not `continue` — `pause`, or `null` (absent: a
  plan authored before the key, or a phase the planner left unmarked);
- the session holds `--pause` (SKILL.md §1);
- a **warning sign** fired during this phase's pass:
  - a gate card rendered — `Audit`, `Doc conflict`, `Tracker drift`, `Tests red`, `Review loop`,
    `Settled item`, `Decision`, `Loop stall` (the emergency ceiling included) — whatever the continuing
    answer was;
  - this pass wrote an override or failure record to the PR body — `## Audit override`,
    `## Plan override`, `## Known failures`, an `Accept current` override, a `## Tracker reconciliation`
    note.

Warning signs only turn `continue` into a pause. Nothing turns a `pause` into `continue`: the planner's
key and the operator's flag are the floor, and "this phase was routine" is a judgment about your own
work. Not warning signs: the S7 follow-up confirmation, settled findings (Plan-settled,
Deferred-by-plan, Refuted), and cold-read findings the loop fixed.

## 3. The phase link

`<pr-url>/files/<entry-sha>..<head-sha>` — the PR's Files-changed view scoped to **this phase's** push.
`<entry-sha>` is this pass's prep `facts.workspace.sha` (the phase's entry HEAD, not the session-entry
SHA the handoff's `Changes:` line uses); `<head-sha>` is `git rev-parse HEAD` in `facts.workspace.path`
after S5.2. When the entry SHA is not a commit in the PR — fresh-mode phase 1, where it is the PR's base
commit and the whole PR is this phase — link `<pr-url>/files`: the discriminating test of
[`../../_shared/handoff-format.md`](../../_shared/handoff-format.md)'s `Changes:` rule. The PR url is
`facts.prior_pr.url`, or the `create-pr` envelope's `url` on a fresh first phase; SHAs in the text are
7-char.

## 4. The checkpoint card

Print one line first, so the link is clickable in the transcript:

> **Phase <N> — <title> shipped** (<K> of <M>) · <phase link> · paused: <`checkpoint: pause` | `--pause` | the warning sign>

Then one `AskUserQuestion` (`header: "Checkpoint"`), its question carrying the phase link and naming the
next phase:

- **Continue here** — description: the next phase's title, `deliverable`, and `closes-dod`.
- **End session** — description: the non-final handoff; the next session starts on a fresh context.

Free text ("Other") is an operator note, and continues. Carry it into the next phase as an Addressable
human comment in iteration 1's input, and record it verbatim in that phase's loop comment (S5.2) so it
reaches GitHub. A note that reverses a locked decision is caught by the fix plan's plan-reversal check
and re-enters the `Decision` card there.

No pause → print the same line ending `· continuing to Phase <N+1> — <title> (checkpoint: continue)`,
and continue.

## 5. Continue

1. Delete this phase's staging files from `facts.scratch` — `pr.md`, `issue-body-projected.md`,
   `review-diff.patch`, `cold-read-diff.patch`, any `slice-<M>-ticked.md`. A surviving fresh-mode
   `pr.md` restaged by a later `edit-pr-body` would overwrite the tracker tick S6 just wrote. The next
   pass's first PR-body write restages from the body the new prep fetched — at that point it *is* the
   body this session last wrote — and S6's "restage from the body this run last wrote" rule governs every
   write after that pass's own S5.2.
2. Re-run prep **in full** — `prep_resolver.py <issue> <owner/repo>`, **no `--refresh`**. `--refresh`
   skips the workspace assertion, so it returns no `facts.workspace` and no reachable
   `facts.tracker.last_shipped` (the next phase's review base). The setup hooks re-run; their
   idempotence contract already covers that. The new facts block replaces the old one wholesale — it now
   reads `vector.mode: continue` on this session's own PR — with one value carried over: the **first**
   prep's `facts.workspace.sha`, the session-entry anchor the handoff's `Changes:` line needs (§6). Note
   it before the first re-run; every later prep reports the next phase's entry instead.
3. Re-enter the spine at **S1** in continue mode (S2 skips there, as it always does) and skip S1.5 —
   the printed line already named the phase. Every per-run state in the spine and its references starts
   over, seeded only from GitHub as a new session's would be: S5.1's loop-entry SHA, the addressed- and
   refuted-items lists, defect counts, the grace round and the ceiling count, the cold read, and any
   guard rail's settled answer.
4. **Warning sign before building.** If this pass's distiller reports `thread-vs-plan: refines`, the
   thread moved during the phase or at the card — a comment the plan never saw. Print the refinement and
   render the `Checkpoint` card before S3, its question naming the refinement: **Continue here** builds
   the plan as refined; **End session** hands off.

## 6. Ending the session

End session (or a hard stop) → the routed playbook's handoff. Its `Changes:` line covers everything this
session pushed — entry = the **first** prep's `facts.workspace.sha` — and, when the session shipped more
than one phase, names each phase's range before the link ([`handoff-renderings.md`](handoff-renderings.md)).
Every resolver re-entry command the handoff carries — the non-final shape's `Next:`, the operator-phase
shape's `Then:` — ends with `--pause` when this session held it; the evaluator-bound shapes cannot carry
it.
