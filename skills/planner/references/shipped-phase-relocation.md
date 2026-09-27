# Shipped-phase relocation

Read by a revise, `revise.md` or `story-jit.md` alike, whenever `facts.plan.shipped.to_relocate` is non-empty **or** `facts.plan.shipped.restore` is present. The format, the keying, and what moves versus what stays are owned by [`../../_shared/plan-shipped-phases.md`](../../_shared/plan-shipped-phases.md); this file is the planner's procedure. Run it on **every** such revise, not only when the body is large: it is mechanical, like an epic's retirement, and a size threshold is exactly the rule three files would disagree about.

`to_relocate` is a prep fact: the phases the open PR's `## Phase tracker` ticks, that are `kind: code-shipping`, and that have no record on this PR yet. Never re-derive it, never widen it, and never relocate a phase outside it — a phase already recorded has an immutable record, and an unticked phase has not shipped.

## Procedure

Run after the revise's "Promote before you drop" step, on the redrafted body in `<facts.scratch>/plan.md`.

1. **Attribute entries to each phase in `to_relocate`.** For each phase, read its shipped diff in `facts.grounding.path` (the open PR head), using the tracker's `(commit <sha>)` as the phase's commit map — `git log --reverse` then `git diff <start>..<end>`, the same extraction the evaluator uses. Then, for each entry in `## Changes (file-level)`, `## Data model / schema impact` and `## Test plan`, decide whether it belongs to that phase. This is judgment: an entry belongs to the phase whose diff delivered it.
2. **Apply the shared-entry rule.** An entry any **unshipped** phase still builds on stays in the main plan, whole. Never split an entry to separate its shipped half. When in doubt, keep it: a kept entry costs characters, a wrongly moved one removes a locked decision from a phase the resolver still has to build.
3. **Stage one record per phase** to `<facts.scratch>/shipped-phase-<N>.md`, in the contract's format: marker line, the `**Shipped on:** #<facts.plan.shipped.pr> · Phase <N> — <title>` line, then the moved entries **byte-for-byte** as they stood in the prior plan under their original headings. A `## Test plan` sub-bullet carries its kind line (`- Unit:`) with it. Omit a heading the phase moved nothing from.
4. **Replace them in the main plan** with the pointer bullet, one per section that lost entries: `- Phases <list> shipped on #<PR>: entries in the shipped-phase records.` The list names every phase with a record on this PR, including records posted by an earlier revise. On a later revise, rewrite the existing pointer rather than adding a second one.
5. **Check it:**

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/plan_shipped.py check "<facts.plan.body_path>" "<facts.scratch>/plan.md" \
     "<facts.scratch>/shipped-phase-<N>.md" ... --pr <facts.plan.shipped.pr>
   ```

   Omit `--pr` only when there is no open PR (`facts.plan.shipped.pr` null). It always exits `ok`. Read `findings` and fix every entry before continuing: `not_verbatim` (a moved entry was reworded — restore the prior text), `still_in_main` (copied, not moved), `missing_pointer`, `foreign_pointer` (a pointer naming a PR other than the open one — see "Restoring a closed PR's records"), `malformed_head`, `unexpected_sections`. `main.headroom_chars` is the size fact; never count characters yourself. Re-run after every restage, alongside the spine's `parse.py phases`.
6. **Review.** Pass the staged record paths to the plan reviewer as `<<shipped_paths>>` (spine S7), alongside the main plan. The records are read-only to the reviewer: a finding can never ask to edit one.

## Restoring a closed PR's records

`facts.plan.shipped.restore` is present when the plan's pointer bullets name a PR that is **not** the open one: a HARD Start-fresh closed it, or it was closed by hand. That PR's records are the **only** copy of the entries its pointers stand in for, and no reader for a new PR follows them, so the plan takes them back:

1. Read `facts.plan.shipped.restore.body_path`. Put every entry back into the main plan, **verbatim**, under the section it came from.
2. Delete the pointer bullets naming that PR. The phases they covered are no longer shipped on any open PR; a later revise relocates them again once they ship on the new one.
3. Leave the closed PR's record comments alone. They are inert, and immutable like every record.

Run `check` without `--pr` when there is no open PR: `foreign_pointer` must come back empty.

## Persist order

On **SOFT-Apply** or **HARD Apply-in-place-anyway**, post each new record **before** the main plan's `edit-comment`:

```bash
${CLAUDE_PLUGIN_ROOT}/scripts/gh_persist.py comment <owner/repo> issue <N> "<facts.scratch>/shipped-phase-<N>.md"
```

Then persist the main plan as the playbook states. If the main edit fails after the records posted, the only cost is content present in both places; the next revise's `to_relocate` already excludes the posted phases. Never post a record after the main edit: a main plan pointing at records that do not exist yet is the one state that loses content.

On **HARD Start-fresh**, post nothing here. The PR is closing, so its records would be inert on arrival. The fresh run that follows has no open PR and nothing to relocate, but prep reports the closed PR's records as `restore`, and it puts them back (see "Restoring a closed PR's records").

## Reconciliation

An entry `check` confirms as a verbatim move is **not** a `## Changes` edit for `revise-reconciliation.md`'s judgment rule, so relocation alone never leans a revise HARD. Show it in the S8 update as one line per phase (`Phase 3: 4 entries moved to its shipped-phase record`), not as deletions.
