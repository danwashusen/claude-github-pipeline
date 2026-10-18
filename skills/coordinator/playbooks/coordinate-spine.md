# coordinator — the turn loop (shared spine)

Every coordinator turn runs these steps, in order. The target's playbook (`epic.md` /
`single.md`) supplies only what differs by shape: which stage comes after which, and what the
operator is told at the ends.

## 1. Prep

Run the router §1 call. On a turn acting on the operator's answer to an open, close or sync card,
pass that action's flag; otherwise pass none. Pass `--story <M>` whenever this run is focused on a
story (the operator named it, the relayed `Next:` named it, or you picked it at `next-story`).

## 2. Verify (on a wake)

When a stage session's end woke you, the stage's own report arrives two ways: the host's
end-of-turn note (short — about 400 characters) and, if the brief was followed, its full
`## Handoff` sent to you verbatim by message. Before reporting anything:

1. Read the new facts. GitHub, through prep, says where the issue is now.
2. Check the stage's claims that matter against them: a claimed merge against `unit.pr.merged`
   and the issue's `closed`; a claimed PR or its draft/ready state against `unit.pr`; a claimed
   close against the target's `state`. A claim the facts contradict is said plainly, with both
   sides.
3. If the stage stopped without finishing — its note says it is waiting on the operator, or
   neither a handoff nor any GitHub change arrived — say where it stopped and that its session
   is still open; offer to re-start that stage only if the operator says the session is gone.

## 3. Reconcile the relayed handoff

Compare the handoff's next command with `next.command`:

- **They agree** (same skill, same target): continue to §4.
- **The handoff names the step after one the coordinator runs itself** — a stage never opens,
  closes or syncs a worktree, so its next command lands one step later: the planner hands off
  `resolver #N` while `next.kind` is `open`; the evaluator's story merge hands off
  `planner #<next>` while `next.kind` is `close` or `pick`; a handoff naming `workspace-open` /
  `workspace-close` names exactly the coordinator's step. That is agreement, never a card: run the
  coordinator's own step (§4) first, and take a story number the handoff names as the pick.
- **The handoff names a route GitHub cannot show** — resolver → planner (re-plan), planner →
  researcher, planner → slicer, anything → drafter (revise), evaluator → slicer (adopt): the
  facts still read the old stage, because a re-route leaves no trace until its stage runs. Render a
  judgment card: the brief quotes the handoff's `Why:` line verbatim; option 1 is the route the
  evidence supports (usually the handoff's — its `Why:` names the evidence), the other is
  `next.command`; each option names the folder from `routes[<skill>]`. The chosen start then goes
  through §4 like any other.
- **They contradict on state** (the handoff says merged, the facts say open): a card, with the
  facts' reading first — GitHub is the authority. Never pick silently either way.
- **No handoff arrived:** proceed on the facts, and say in one line that no handoff came back.

Milestone updates the stage sent while it ran, and any announced choice in them, are relayed to
the operator in one line each, as they arrive.

## 4. Offer the next step, by `next.kind`

- **`session`** — report in one or two lines, then end the turn offering the start (router §3): the
  one-click answer carries `next.command` and `next.folder`. When `next.sync_first` is true, the
  offer names the sync too ("Sync the epic worktree, then start planner #152 in <folder>"). When an
  `attention` line warns that the project root is not at the default tip, say it in the offer —
  the session would refuse its checkout — and leave moving the checkout to the operator.
- **`open` / `close`** — a consent card. Its brief says what happens: an open creates the branch
  linked to the issue on GitHub, `.worktrees/<branch>`, and runs the setup hooks; a close runs the
  teardown hooks and removes the worktree (the branch and the PR stay). On yes, re-run prep with
  `--open <next.issue>` / `--close <next.branch>`, report the receipt in one line, and continue
  with the new `next` in the same turn.
- **`pick`** — choose the next story: the relayed `Next:` when it names one of `epic.candidates`;
  otherwise the first candidate in the epic plan's story order (read the plan at `epic.plan_path`
  when one is given), announced in one line (`Picked #N because …; say if you'd rather #M`). Then
  re-run prep with `--story <N>` and continue.
- **`none`** — `refused` and `gated` render their card (router §2); `terminal` ends with the
  summary (router §4).

## 5. Start the stage (on the operator's click)

The click arrives as the operator's own message naming the command and folder. Then, in this
order:

1. If the go-ahead named a sync, run prep with `--sync` first. A card from it is rendered and the
   start waits for it; a successful sync is reported (`receipt.sync.before` → `after`, or "already
   at the tip").
2. Where a session-start tool is available, start a **fresh** session in that exact folder — the
   folder as it is, no new worktree — with the brief from
   [`../references/stage-brief.md`](../references/stage-brief.md) filled in, the effort the
   operator set for this run (else inherited), and a request to wake you when it finishes.
3. Send the new session one short message right away, so it has your address for its updates and
   its handoff.
4. Report the start in one line, linking the session, and end the turn.

Where no session-start tool is available, print the command in its own fenced block and the folder
to run it in, and say: "run it there, then tell me when it's done". The operator's "done" starts the
next turn at §1.

## 6. While a stage runs

The stage's decision cards are mirrored into this chat with the text printed beside them, and the
operator may answer in either session. Never answer one, and don't restate it; if the operator asks
about one, say which stage and issue it belongs to (its identity line names them). Relay milestone
updates in one line each. Start nothing else for this issue until the stage ends.
