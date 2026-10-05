# Finalisation — the operator's polish triage on the final pass

Read at S5.2 on the **final** pass (S5.1 "Scope": a single-phase issue, the last unshipped code-shipping
phase, or a revision run), before the push. The polish the review loop leaves on the `## Polish` ledger
([`../../_shared/polish-ledger.md`](../../_shared/polish-ledger.md)) used to wait for the evaluator, and
applying any of it there cost a soft-reject, a whole revision session and a second evaluation — while the
operator usually wanted it applied. Finalisation puts every undecided entry to the operator while this
session is still here, so an applied entry costs one fix round and the phase still pushes **once**. The
evaluator's S5.5 stays the backstop for whatever is still `open` when the PR reaches it.

## 1. When it runs

- **The exit.** S5.1 exited on a settle or an **Accept current**. A terminating guard-rail answer
  (**Re-plan**, **Restructure**, **Abort**, **Abort loop**) skips it: the run is not handing the PR
  forward.
- **The final pass only.** A non-final phase's leftovers wait — a later phase may fix or remove the site,
  and the final pass triages the whole ledger at once. A trailing operator / decision-only phase changes
  nothing: finalisation runs on the last code phase, and the session then takes the operator-phase
  handoff.
- **Once per pass.** When finalisation's round re-enters S5.1 (§4) and S5.1 exits again, go straight to
  the push — never a second finalisation.
- **Nothing to triage → skip it silently**: no card, no loop-comment line.

## 2. The entries

- every `facts.polish` entry marked `open` — earlier phases' leftovers, from the PR body this pass's prep
  fetched (none in fresh mode);
- this pass's unfixed polish, which the fix rounds held for S5.2. Mint each one's id now, per
  `polish-ledger.md` "Format": `P<phase>.<seq>`, a revision run recording under the last
  `kind: code-shipping` phase's number, `<seq>` continuing from the highest existing one.

An `apply` entry is not triaged: it is decided, and iteration 1 already treated it as Addressable — one
this pass left unfixed stays `apply`, and the evaluator re-proposes it. `file`, `drop` and `applied`
entries are decided records.

## 3. Triage

Run [`../../_shared/polish-triage.md`](../../_shared/polish-triage.md) with:

- **the checkout** — `facts.workspace.path` at HEAD (local: nothing is pushed yet);
- **the plan** — `facts.distiller_bundle.plan_marker_path` (with `plan_shipped_path` when present), and
  `facts.dod`, for the scope test;
- **the apply bar** — finalisation's (that file's "The apply bar"): in scope, true at head, clearly right
  rather than taste;
- **"Other"** — besides a split answer, it may leave entries for the evaluator: they stay `open`, and S5.5
  asks about them.

The `Polish` card is a gate SKILL.md "Gates only for genuine decisions" names. When S5.1 exited on
**Accept current**, say so in the card's question, so the operator weighs **Apply in this PR** against a
loop that stalled.

An entry the re-check shows is a real **defect** is not polish: record it `drop` with the note
`reclassified: defect — see loop comment`, and fix it in §4's round as a defect-tier item.

## 4. Apply

With any **Apply in this PR** answer — or a reclassified defect — run one fix round, S5.1 step 2 per
[`review-fix-round.md`](review-fix-round.md), whose input is those entries: each applied entry Addressable
whatever its tier and built to its note's `intent:` when it carries one. The round runs in full — the fix
plan checked as a set, fix design on a hot seam, defect injection, the §10.6 gate, one commit, the staged
reply. Then continue at S5.1 step 3:

- **Every fix was polish** → the round settles and takes step 3's one **light re-review** (`review` at
  `medium` over the round's commit). A defect it finds re-enters the loop at step 2 under step 3's rules,
  the reset rule's fresh baseline included; polish it finds goes to the ledger `open`, unfixed — for the
  evaluator, never back to this card.
- **The round fixed a reclassified defect** → step 3's ordinary rules: the loop runs on until it settles.

The round counts toward S5.1's emergency ceiling. A fix plan whose check finds an applied entry reverses a
plan decision renders the `Decision` card, as in any round. Each applied entry becomes
`applied (commit <sha>)` with that round's commit.

## 5. Re-plan

A **Re-plan** answer records `apply` with the note prefixed `operator: re-plan —`. Fix the plain **Apply
in this PR** entries first in §4's round, except any that share a site or seam with a re-plan entry —
doubt means coupled, and those wait for the re-plan. Then push at S5.2 and take the routed playbook's
**Re-route → planner** handoff to `/github-pipeline:planner revise #<issue>` — no ready flip. Its `Why:`
quotes each re-plan entry by id and the decision its note names (`handoff-format.md` re-route rules).
The planner's polish re-route places the work — a new phase on a multi-phase PR, folded into the one
phase on a single-phase PR, where the next resolver run is a revision run on `polish_apply` — and the new
last phase gets its own finalisation.

## 6. The record

Write the answers into the ledger at S5.2 with this pass's other entries — the staged `pr.md` in fresh
mode, the restaged body through `edit-pr-body` in continue mode: `applied (commit <sha>)`, `file` (its
`group:` note), `drop`, `apply` (a re-plan), and `open` for whatever is left. `file` entries are filed
after the merge by the evaluator's residual step, never here — a PR that never merges files nothing.

Stage one line into the loop comment after the round's reply — `Finalisation: applied <ids>; file <ids>
(<group>); drop <ids>; re-plan <ids>; left open <ids>`, omitting empty parts — so the decision reaches
GitHub. The handoff's `Why:` names the same outcome by id ([`handoff-renderings.md`](handoff-renderings.md)).
