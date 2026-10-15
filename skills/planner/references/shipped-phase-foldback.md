# Shipped-phase fold-back

Read by a revise, `revise.md` or `story-jit.md` alike, whenever `facts.plan.shipped.present` is true. Until 4.35.0 a revise moved each shipped phase's `## Changes (file-level)` / `## Data model / schema impact` / `## Test plan` entries out of the plan into a per-phase record comment, leaving a pointer bullet behind ([`../../_shared/plan-shipped-phases.md`](../../_shared/plan-shipped-phases.md)). Those sections now live in the plan's own build part ([`../../_shared/plan-parts.md`](../../_shared/plan-parts.md)), so nothing writes a record, and this revise puts every record's entries back. It is mechanical and runs on every such revise, not only a large one.

`facts.plan.shipped` is a prep fact: every record the plan's pointer bullets name, on whichever PR (the open one, or one a Start-fresh or a hand closed), staged together at `facts.plan.shipped.body_path`. Never re-derive it.

## Procedure

Run after the revise's "Promote before you drop" step, on the redrafted body in `<facts.scratch>/plan.md`.

1. **Put every entry back, verbatim,** under the section it came from in the record, beside the plan's own entries for that section. A `## Test plan` entry goes under its kind line (`- Unit:`), which the plan carries once, never once per record. Order by phase, so the entries read in the order they shipped.
2. **Delete every pointer bullet** (`- Phases … shipped on #<PR>: entries in the shipped-phase records.`). Nothing will ever write the records a pointer would lead to.
3. **Check it:**

   ```bash
   ${CLAUDE_PLUGIN_ROOT}/scripts/plan_shipped.py check "<facts.scratch>/plan.md" \
     --restored "<facts.plan.shipped.body_path>"
   ```

   It always exits `ok`. Fix every finding before continuing: `not_restored` (an entry dropped or reworded — restore the record's text) and `pointer_left` (a pointer bullet still in the plan). Re-run after every restage, alongside the spine's `parse.py phases`.
4. **Leave the record comments alone.** With no pointer naming them they are inert, and nothing deletes them.

The folded-back entries are the shipped phases' detail, and the reviewer already knows those phases shipped (`<<shipped_phases>>`, spine S7). The build part's own cap now bounds them; when `split` reports it `over_limit`, compact per plan-schema.md, "Size" — the fold-back is never the thing to skip.

## Reconciliation

An entry `check` confirms as restored verbatim is **not** a `## Changes` edit for `revise-reconciliation.md`'s judgment rule, so folding back alone never leans a revise HARD. Show it in the S8 update as one line (`Phases 1–3: entries folded back from their shipped-phase records`), not as additions.
