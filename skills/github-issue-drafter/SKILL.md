---
name: github-issue-drafter
model: opus
effort: high
description: Drafts well-structured GitHub issues from informal developer feedback and files them via the `gh` CLI. Use this skill whenever the user describes a bug they hit, an incomplete or half-built feature they noticed, or a new feature idea — and wants it captured as a GitHub issue. Trigger this even when the user does not explicitly say "make an issue" — phrases like "I should track this," "let's file this," "we need to remember to fix X," "log this for later," or simply describing a problem in a repo context all qualify. Also use this skill to **revise an existing issue** when the user references one by number/URL with revision intent — phrases like "revise #N," "update issue #N," "improve #N," "does #N still match the docs?", or "rewrite the description of #N." Also use it to **file or track an open question / decision request** for one or more named audiences (business, architect, developer, UX, …) as a `question`-type issue labeled by audience — but only on an explicit capture verb: "file/open/log/track a question," "capture this decision for the architect," "raise an issue to ask the business," or "track `PRD-OQ-06b` as an issue." A bare decision-question with no capture intent ("should we use phone or video?") is asking for *your* answer and is **not** a trigger; naming an audience alone ("the business should weigh in on this") isn't one either without a file/track/log verb. Works best when the user is inside a git repository directory. Uses repo issue templates and labels if they exist, otherwise applies a consistent built-in format. Reads the project PRD (if one exists at `docs/prd.md` or similar) to ground feature framing and surface tensions between feedback and spec. Every drafted or revised issue is automatically validated by an isolated review sub-agent that checks the issue against the project's PRD, architecture, constitution, and current codebase before the user sees the final draft.
---

# GitHub Issue Drafter

Turn informal developer feedback into well-structured GitHub issues. The user is mid-development on a product and notices things — bugs, gaps, ideas. Your job is to capture those cleanly so future-them (or their team) has enough context to act.

This skill is the first stage of a pipeline: it files the issue; `github-issue-planner` later researches and attaches a verified implementation plan (stored as a comment, not in the body); `github-issue-resolver` then builds it. The practical consequence for **revise mode** is that an issue you drafted may have a plan comment attached after the fact — leave that comment alone, preserve its body pointer, and flag when a body revision may have invalidated it (see Revise mode).

### Asking the user a decision

When you need a decision from the user — an approval gate, a disambiguation, or a confirmation before a GitHub write — follow the shared contract in [`../_shared/asking-the-user.md`](../_shared/asking-the-user.md): one decision per `AskUserQuestion` card, `header` ≤ 12 chars, imperative `label`s with consequence-bearing `description`s, options generated dynamically when the candidates aren't fixed, and the rule that a sub-agent never calls `AskUserQuestion` itself but surfaces a "decision needed" signal back to this main loop. That file is the single source of truth for every gate in this skill.

### Delegating mechanical work to `github-ops`

The judgment in this skill — classification, PRD-tension calls, drafting, applying
review findings — is what's worth a high-effort model. The judgment-free I/O is
not: fetching an issue + thread for revise mode, reading referenced issues,
checking templates/labels, and the `gh issue create` / `gh issue edit` writes.
Delegate that to the **`github-ops`** sub-agent (`subagent_type: "github-pipeline:github-ops"`,
Sonnet + medium effort — spawn with **no `model` override**). It runs a named
operation and returns faithful structured results: `GATHER_ISSUE`,
`PERSIST_BODY`, `PERSIST_CREATE` — see `../../agents/github-ops.md`. It
returns bodies and threads **verbatim** so the classification and
latest-direction judgment stay yours. Codebase searches for coherence checks
do **not** go through `github-ops` (it's the GitHub-I/O executor) — use
`Grep`/`Glob` directly, or spawn an `Explore` sub-agent for broader sweeps.

Two guardrails carry over from the reviewer: `github-ops` cannot call
`AskUserQuestion`, so on any ambiguity (issue not found, >1 plan comment, a body
edit it can't safely reconcile) it returns `DECISION_NEEDED: <…>` and writes
nothing — surface that here and re-dispatch. And every `PERSIST_*` runs only
**after** the orchestrator's filing gate has cleared — the user's step-6 confirmation
for single issues and revisions, or a clean pass through the adversarial split loop +
body review for the Epic one-shot batch (see "One-shot filing flow"); either way
`github-ops` posts the approved title/body verbatim and never authors content.

## The core loop

1. **Classify** the feedback: bug, incomplete feature, new feature, Epic, or question.
2. **Check the repo** for existing conventions (templates, labels) — use them if present.
3. **Gather missing context** by asking the user, but only what's actually needed.
4. **Draft** the issue (title + body + labels + priority).
5. **Run the sub-agent review loop** and fold in findings (up to 3 passes). See "Sub-agent review loop" below.
6. **Show the draft** (with any unresolved review findings) to the user and wait for confirmation.
7. **File** via `gh issue create` only after the user approves.

Never skip step 6. Filed issues are annoying to clean up, and a 10-second confirmation prevents that. (The one exception is the Epic one-shot batch — see "One-shot filing flow" — where the adversarial split loop plus the per-story body review stand in for the gate and a clean pass through both files the set autonomously.)

For revising an **existing** filed issue (when the user references one by number with revision intent), use the parallel flow in "Revise mode" below — same review loop, but starting from a `gh issue view` instead of a fresh draft and ending in `gh issue edit` instead of `gh issue create`.

## Revise mode

Triggered when the user references an existing issue with revision intent: "revise #N," "update issue #N," "improve #N," "does #N still match the docs?", "rewrite the description of #N," and similar. Issues drift — the codebase moves, decisions in the comment thread supersede the original body, the PRD changes — so this mode exists to refresh a stale issue against today's reality without re-filing.

The flow mirrors the core loop, but starts from a filed issue and ends in `gh issue edit`. It shares the sub-agent review loop with new-issue drafting (step 5 in the core loop).

### Step R1: Identify the issue

Parse the issue number or URL from the user's message. If the user said something ambiguous like "the dashboard ticket," ask which one — same rule as in "Detecting related issues."

### Step R2: Fetch the issue and its full thread

Delegate the fetch to `github-ops` so you read everything in one pass before forming an opinion:

> `GATHER_ISSUE(issue=<N>, repo=<owner/repo>, marker_prefix="<!-- implementation-plan:v1 -->", extra_json="closedByPullRequestsReferences,projectItems", scratch_dir=/tmp/gh-drafter-<N>/)`

The `## RESULT` envelope returns scalars + path references — `issue_body_path`, `thread_path`, and (when a plan exists) `marker_comment_id` / `marker_comment_url` / `marker_comment_path` — plus the closed-by-PR / project references and the open-PR list. `Read` the body and thread from their paths. When a plan marker exists, `Read` it from `marker_comment_path` to ground the revise against the same approach the resolver is bound to.

If a PR exists, surface it before editing — the user may want to coordinate, or to wait until the PR merges before reshaping the issue body.

If a plan comment came back, note its URL — you'll preserve the body's plan pointer and flag staleness at Step R6. **Never edit or delete the plan comment itself**; it's the planner's artifact, refreshed only by re-running that skill.

### Step R3: Identify the latest direction from the thread

Long threads matter. The original body is often outdated by the time someone asks you to revise it — the substantive direction-setting may have happened five comments down. Earlier proposals are superseded if a maintainer or the OP has agreed to a different approach. Don't re-litigate decided questions.

Write a one-line state summary the user can correct before you do any work:

> "Original body says X; comment thread by @maintainer on 2026-04-12 agreed to do W instead — I'll revise toward W. Correct?"

This anchors the rest of the response and lets the user adjust if you've misread the thread.

### Step R4: Run the review loop on the existing body

Same loop as for drafts (see "Sub-agent review loop" below). Feed the sub-agent the existing title + body + labels + the type (bug | incomplete | feature | epic | story | question). Mode is `revise <N>` — the sub-agent fetches the live state for itself and walks the comment thread under the latest-decisions dimension.

**Reconcile open questions.** Re-run Step 2's detection against the current source and the issue's existing `## Open questions` section. Add entries for newly-opened OQs (match first, per Step 3.5). For an OQ whose companion question is now **resolved** — read via the tiered status read (a `closed` question, or `resolved-in-thread` for one still open; see [`../_shared/open-question-links.md`](../_shared/open-question-links.md) §"Status is the tracker's"), not a doc register field — surface it in the R5 diff ("`OQ-05`'s question #N is answered; its scoped-out part can be re-filed as a follow-up, and any native `blocked by` on it removed (`PERSIST_LINK(remove_blocked_by=#N)`) — want me to?") rather than silently deleting the entry. The drafter reconciles the section; it never resolves the OQ itself.

### Step R5: Show a diff-style draft

Don't repaint untouched sections. Show only what changes:

```
Title: Old → New      (omit if unchanged)
Labels: + new-label, - removed-label   (omit if unchanged)

Body changes:
## <section> (changed)
<old> → <new>

## <section> (added)
<new>

## <section> (removed)
(no replacement)
```

If a section is unchanged, just say "(other sections unchanged)" — the user doesn't need to re-read the whole body.

### Step R6: Confirm and apply

Wait for explicit confirmation. Then:

**Preserve the plan pointer.** If the issue body carries a `> 📋 **Implementation plan:**` pointer line (added by `github-issue-planner` at Step R2's check), keep it verbatim in the revised body — don't drop it, don't duplicate it, don't touch the plan comment it links to.

**Flag a possibly-stale plan.** If a plan comment exists and this revision materially changes scope, acceptance criteria, or the contracts the plan was built against, the plan may now be stale. Tell the user once after applying the edit: "This revision changed <scope/AC/contracts>; the implementation plan on #N may now be stale — re-run `github-issue-planner` in revise mode to refresh it." The drafter does not edit the plan; refreshing it is the planner's job.

**Stage the revised body to disk before dispatching.** Write the full revised body (with the `📋` plan pointer preserved verbatim if present) to `/tmp/gh-drafter-<N>/revised.md`. `github-ops` reads the bytes from that file via the bundled `gh-persist.sh` script — you pass the path, not the contents. The body never travels through the dispatch prompt, so prompt compaction can't abbreviate it and an in-agent Write/Bash race can't lose it (the same combination that filed empty bodies on #626/#627). What the caller writes to disk is what posts to GitHub, byte-for-byte.

Hand the approved revision to `github-ops` (it preserves the plan-pointer line because you wrote it into `revised.md`):

> `PERSIST_BODY(issue=<N>, repo=<owner/repo>, mode=replace, body_path=/tmp/gh-drafter-<N>/revised.md, title=<new title if changed>, labels_add=<…>, labels_remove=<…>)`

Pass only the deltas — omit `title` if unchanged, omit `labels_*` if there are none. If `github-ops` returns `DECISION_NEEDED: PERSIST_BODY(replace) called with empty body file at <path>`, the staged file came back empty or missing — re-write `revised.md` from your in-memory body and re-dispatch with the same path. The script's `test -s` gate is the only thing standing between a missed staging step and a live-body wipe. `github-ops` returns the issue URL plus a `body_sha256` you can cross-check against `shasum -a 256 /tmp/gh-drafter-<N>/revised.md`; share the URL with the user.

### Special case — revising an Epic

After revising the Epic body, also re-audit child stories. Get the reconciliation from `github-ops` — `GATHER_EPIC(epic=<epic-#>, repo=<owner/repo>, scratch_dir=/tmp/gh-drafter-<epic-#>/)` returns `epic_body_path` and each `## Stories` entry as `{number, title, checked, state}` inline scalars, pairing the body checkbox with the story's live state. `Read` the epic body from `epic_body_path` to ground the re-audit, then reconcile the checkboxes against the live state (closed → checked; open → unchecked) and run the **dependency-graph story-ordering check** (dimension 5) and the **story-sizing / over-split check** (dimension 7) against the current set of stories. If ordering or sizing findings come back, surface them with evidence and a proposed re-ordering or merge — the user confirms before the body is edited. Don't silently swap or merge bullets. (A sizing finding on an already-filed Epic can't un-file a story; surface it as a recommendation — "stories #N and #M could have been one" — for the user to act on, e.g. by closing one as part of the other's work.)

### Special case — revising a Story

Verify the `**Epic:** #<epic-#>` backlink still points at an open Epic. If the Epic has closed, surface that and ask via `AskUserQuestion` (header "Epic closed"): **Close the story** — retire the Story since its Epic is done; **Detach backlink** — remove the `**Epic:**` line and leave the Story standalone; **Relink to epic** — point the backlink at a different open Epic. Don't quietly leave a Story dangling under a closed Epic.

## Step 1: Classify the feedback

The three types map to very different structures, so getting this right matters. Use these cues:

- **Bug** — Something is broken or behaving wrong. Cues: "X is broken," "this throws an error," "Y doesn't work when Z," past-tense problem reports, error messages, unexpected behavior.
- **Incomplete feature** — Something half-built that the user noticed while working on it. Cues: "I never finished," "this only works for X but not Y," "the empty state isn't handled," "TODO," "we stubbed this out."
- **New feature / enhancement** — A capability that doesn't exist yet. Cues: "users should be able to," "it would be nice if," "we need a way to," "I want to add."
- **Epic** — A multi-capability initiative too big to ship as a single PR; it decomposes into several Story issues. Cues: user lists multiple distinct capabilities in one breath ("we should do X, then Y, then Z"), scope crosses layers (UI + data + service), explicit phrasing like "this is going to be a big one," "multi-phase," "initiative," or the word "epic" itself. Heuristic: if the acceptance criteria the user has in their head won't fit in one shippable PR, it's likely an Epic.
- **Question** — A request for a decision or an answer from a human, not a unit of work to build. Cues: "I need an answer for X," "open question," "we need to decide," "should we …," "who can confirm …," or a reference to a tracked-questions id (e.g. `PRD-OQ-06b`). The tell is that *no code follows from filing it* — someone has to answer first. A question is categorically different from the other types: it doesn't enter the research/plan/build pipeline and its handoff is terminal (see the "After filing a question" subsection in Step 7 and the question rendering in Step 8). When feedback bundles a question with work ("should we cache this, and if so add a cache layer"), file the question first and let its answer drive whether the work issue gets filed.

**Feature vs. Epic — ask, don't promote.** Scope is the user's call. When detection signals fire, confirm rather than silently upgrading — ask via `AskUserQuestion` (header "Issue size"): **One feature** — file it as a single feature issue; **Epic + child stories** — open an Epic and break the work into child stories. Filing a feature when the user wanted an Epic (or vice versa) is annoying to undo.

If genuinely ambiguous between bug / feature / epic, ask the user — don't guess. A bug filed as a feature (or vice versa) creates triage friction later.

## Step 2: Check the repo

Run these checks once before drafting (cheap, and keeps the issue consistent with whatever conventions exist):

```bash
# Verify gh is authenticated and we're in a repo
gh repo view --json nameWithOwner,defaultBranchRef -q '.nameWithOwner'

# Look for issue templates
ls .github/ISSUE_TEMPLATE/ 2>/dev/null

# Pull existing labels (so you can pick real ones, not invent them)
gh label list --limit 100

# Look for a PRD (Product Requirements Doc)
ls docs/prd.md docs/PRD.md PRD.md prd.md 2>/dev/null
```

**If issue templates exist:** Read the relevant one and follow its structure. Templates encode the team's expectations — don't override them.

**If labels exist:** Map the feedback to existing labels. Don't invent `bug` if the repo uses `kind/bug`. Don't make up priority labels if the repo uses `P0`/`P1`/`P2` instead of `priority:high`.

**If a PRD exists:** Read it. Treat it as authoritative for what the product is supposed to do, but understand that PRDs evolve — so this skill's job is to surface tensions, not enforce the PRD as immutable. See "Using the PRD" below.

**If neither templates nor labels exist:** Use the built-in templates below. Suggest creating standard labels at the end (don't auto-create them — that's a repo-level decision).

### Detecting open questions in the source

While gathering context for a **build** issue (bug/feature/incomplete/epic/story) you read across the docs that ground it — a PRD section, a UI/design spec, an architecture note. Any of them may carry an **unresolved open question** (OQ) on the very scope you're about to spec: a decision the team hasn't made yet, surfaced inline as `PROVISIONAL — <oq-id>` / `TBD` and similar. Building on an undecided OQ silently freezes a decision that isn't yours to make — so watch for them as you read.

Detect and match OQs per [`../_shared/open-question-detection.md`](../_shared/open-question-detection.md) (config-block hint + heuristic cues + the tracker de-dup search — the single source of truth; don't restate it). Scope here is **this issue**: only the OQs that gate the scope you're drafting, not a project-wide sweep. When one gates the issue, resolve it at **Step 3.5** and record it per [`../_shared/open-question-links.md`](../_shared/open-question-links.md) (the `## Open questions` schema, dispositions, and native-dependency rule).

**Thin safety net.** The drafter no longer owns cross-doc detection, registry reconciliation, or doc back-linking — those are the `open-questions` sweep's (`/github-pipeline:open-questions`). But it must not **silently freeze** an untracked OQ into an issue's Definition of done: if you spot an OQ gating this issue, surface it and give it a Step 3.5 disposition rather than baking the undecided part in.

## Using the PRD

When a PRD is present, read it before drafting and use it in three ways:

1. **Ground the language.** If the PRD names personas ("creator," "reviewer," "admin"), use those names in user stories rather than inventing new ones. If it uses specific terminology for features or capabilities, mirror that. This keeps issues searchable and consistent with the wider product narrative.

2. **Detect tension between the feedback and the PRD.** Three patterns to watch for:
   - **The feedback contradicts the PRD.** E.g., the PRD says "users cannot edit submitted forms" and the user wants to file an issue requesting an edit-after-submit feature. Either the PRD is out of date or the feature shouldn't ship as described — flag it.
   - **The feedback extends the PRD into territory the PRD doesn't cover.** Common for incremental product work. Worth flagging because it implies the PRD may need to grow.
   - **An "incomplete feature" report describes a gap between what's built and what the PRD specified.** This is useful framing — the issue isn't just "feature X is incomplete," it's "feature X doesn't match PRD section Y." Cite the relevant section.

3. **Add a "PRD impact" note in the draft when there's tension.** A short section near the bottom of the issue body, like:

   ```markdown
   ## PRD impact
   This <extends | contradicts | clarifies> the PRD (section: <name or quote>). The PRD may need to be updated to reflect <what>.
   ```

   When there's no tension — the feedback fits cleanly within what the PRD already describes — omit this section. Don't add it just to show you read the PRD.

**Authoritative but mutable.** The PRD wins on framing and terminology by default, but if the user's feedback genuinely conflicts with it, surface that explicitly — state the conflict ("The PRD currently says X, but your feedback suggests Y") and ask via `AskUserQuestion` (header "PRD conflict"): **File to update PRD** — file the issue as a request to change the PRD; **File the feature** — file the feature as described, treating the PRD as the thing that's out of date; **Flag for discussion** — file it but flag the conflict for the team to resolve. The user decides which way to go — don't silently override either the PRD or their feedback.

**When the PRD is most relevant:** new features (heavily — they extend or contradict scope) and incomplete features (moderately — gaps often map to PRD sections). Bugs rarely touch PRD; only mention it if the bug is actually a spec mismatch rather than a defect.

## Detecting related issues

Before drafting, scan the user's feedback for references to other issues. People naturally bring these up when filing — "this is like #45," "may be fixed by #21," "see also https://github.com/.../issues/78" — and capturing the relationship in the issue body makes triage dramatically easier.

**What to look for:**

- Issue URLs (`https://github.com/.../issues/N`)
- Shorthand references (`#N`)
- Phrasings like "issue 21," "the dashboard ticket," "that bug we filed last week"
- PR references — sometimes the user's feedback relates to in-flight work, not just other issues

If a reference is ambiguous (e.g., "the dashboard ticket"), ask which one rather than guessing.

**Read the referenced issues** before drafting:

```bash
gh issue view <N> --json title,state,body,labels
```

This is cheap and prevents the skill from misframing the relationship — e.g., calling something a duplicate when it's actually about a different component.

**Classify the relationship** based on how the user described it:

| User said something like... | Relationship | Phrasing in body |
|---|---|---|
| "this should behave like #78 says" | **Defines expected behavior** | `Expected behavior is described in #78.` |
| "may be resolved by #21," "might already be fixed by..." | **Possibly resolved by** (uncertain) | `May be resolved by #21 — verify once that work lands.` |
| "blocked by #50" | **Blocked by** | `Blocked by #50.` |
| "duplicate of #99," "same as #99" | **Duplicate** | `Duplicate of #99.` |
| "related to #12," "see also #12" | **Related** (loose connection) | `Related to #12.` |
| "this closes #5," "fixes #5" — only when user is unambiguous | **Auto-close** | `Closes #5.` |

**Do not use auto-close keywords** (`closes`, `fixes`, `resolves`) unless the user explicitly said this issue resolves another. Those keywords cause GitHub to auto-close the referenced issue when this one closes — a side effect the user must opt into. When in doubt, use `Related to #N` instead.

**Render relationships in the issue body** under a `## Related issues` section, placed near the bottom (after Acceptance Criteria / Definition of Done / Environment, before any "PRD impact" note). Mirror the user's hedging — if they said "may be resolved," the draft says "may be resolved." Don't upgrade uncertainty into certainty.

```markdown
## Related issues
- Expected behavior is described in #78.
- May be resolved by work on #21 — verify once that work lands.
```

If there are no references, omit the section entirely. Don't fabricate relationships.

**A `Blocked by #N` relationship also sets a native dependency.** When you render `Blocked by #N`, additionally set GitHub's native `blocked by` relationship so the block is structured (visible in the UI, and gated on by the resolver/evaluator), not just prose — pass `blocked_by=#N` on the `PERSIST_CREATE` at file time (or `PERSIST_LINK(add_blocked_by=#N)` when the reference surfaces after the issue exists). This is **capability-gated**: `github-ops` drops it with a `DEPS_UNSUPPORTED:` notice on a repo/gh without native dependencies, and the prose `Blocked by #N.` line is the always-present fallback — so keep the prose line regardless. (The other relationships stay prose-only; only `Blocked by` maps to a native dependency.)

**One nuance worth surfacing to the user:** if the user said "this may be resolved by #21," that's a hint they're unsure whether to file at all. It's worth a quick "I'll file this with a note that #21 might already cover it — or do you want to wait and check #21 first?" Most users will say file it anyway (cheap to close as duplicate later), but giving them the choice respects their time.

## Epics and child stories

### When Epic applies

An Epic is for work where each child is **independently shippable** — a separate PR, separate review, separate merge. Don't use Epic just because a feature has several acceptance criteria; use it when those criteria represent distinct deliverables a developer could pick up one at a time. If in doubt, ask the user.

### Sizing stories: coalesce thin slices

"Independently shippable" is a ceiling, not a target. It tells you when work *can* be split; it says nothing about when it *shouldn't* be. Splitting has a cost the issue body never shows: every story a developer picks up pays a fixed tax — a fresh worktree (and any per-worktree resources it provisions — a simulator, a test database, a bound port), a static-check baseline, a cold build or app boot, a targeted test run, and a full review-loop round-trip — before any of its actual work counts. A 40-line story and a 400-line story pay almost the same tax. Slice too thin and that tax dominates: ten trivial stories can cost more wall-clock in setup, testing, and review than three substantial ones that deliver the same thing.

So aim for the **coarsest** slicing that still keeps each story independently shippable. After you have a candidate story list, make a coalescing pass over adjacent slices and **merge** a pair (or cluster) when any of these fire:

1. **Shared verification surface** — the slices would re-run the *same* expensive verification: the same build, the same integration-test target, the same golden/snapshot set. Splitting them means paying that verification twice for one logical change. (E.g. two new screens mounted by the same container that share one snapshot suite — review them together, with both visible in context.)
2. **Sequential with no standalone value** — one slice exists only to feed the next and delivers nothing a reviewer could sign off on its own. A 20-line wiring change that's meaningless until the view it wires lands is part of that view's story, not its own. Likewise, deleting a legacy component once its sole consumer has been rewired is the second half of that rewire — fold it into the integration story, not a standalone "remove the old thing" story.
3. **Same files or layer, individually thin** — several small edits to the same files or layer that a reviewer would naturally read as one change. Bundling them saves N−1 review cycles on the same surface.

**Guardrail — don't over-coalesce.** Keep slices separate when each has independent value, a clean contract, *and* a cheaper isolated test surface. The clearest case is a layer of pure functions or models whose tests are fast unit tests with no build/UI/snapshot cost: splitting them doesn't duplicate any expensive verification (signal 1 never fires), the contracts stay crisp, and they can land in parallel. Thin is not the same as mergeable — a small slice that introduces a real contract worth reviewing on its own (a schema field, a new public type with its own test suite) earns its own story. The point is to stop paying the *fixed tax* twice for one logical block, not to bulk up every story.

### One-shot filing flow

Epics file in a single pass: draft the Epic and full bodies for **all** its stories, review the whole set, then create everything together. There's no "file the Epic now, promote bullets later" mode — a half-filed Epic with placeholder bullets is exactly what this flow exists to avoid. The granularity is settled *before* anything is created, so a bad split costs a draft edit, not a round of `gh issue close`.

**Step E1 — Settle the split (adversarial sub-agent loop).** Produce the candidate story list — each a short title plus a one-line scope that names the files, layer, and test surface it will touch (the reviewer needs that to judge sizing). Apply the coalescing pass yourself first. Then hand the split to the review sub-agent in **split mode**: its job is adversarial — find the strongest case the split is *wrong*, in either direction. Too granular (slices that should merge per the three signals) or over-coalesced (independently-valuable, clean-contract slices collapsed past the guardrail), plus ordering errors (dimension 5). Because it reasons from scopes, not full bodies, it **greps the codebase to ground every surface-overlap claim** rather than asserting it. Apply its merges/reorders and re-run. Loop until it returns clean, under the standard loop control (3-pass cap + circular guard — see "Loop control"). This loop runs dimensions 5 and 7 only; the per-story content dimensions come next, once bodies exist.

**Step E2 — Draft bodies and confirm the review.** For the settled split, draft the Epic body and every Story body (each with its `**Epic:** #<epic-#>` backlink — see "Story body shape"). Run the review loop over the set: dimensions 1, 2, 3, 6 on each Story body and the Epic body, and **re-confirm 5 + 7 on the real bodies** — a body sometimes reveals a slice is materially bigger or smaller than its one-line scope claimed, and that's the moment to catch it.

**Step E3 — File the batch (hands-off on a clean run).** This is the one place the Epic flow departs from the skill's "never file without an explicit go-ahead" rule, deliberately: when E1 and E2 both come back clean, file the whole set autonomously — no confirmation gate. The adversarial split loop and the per-story body review *are* the safety net here, standing in for the human confirmation; a clean pass through both is the go-ahead. File the Epic, then each Story (collecting `#NN`), then patch the Epic's `## Stories` bullets to real links (see "Filing an Epic with child stories" in Step 7).

Pull the user in **only** when a loop didn't come back clean: the split loop hit its cap or circular exit (Step E1), or a body review surfaced a BLOCKER you couldn't resolve (Step E2). Then show the set + the unresolved findings and wait — the same cap/circular handling used everywhere else in the skill. And on a mid-batch `gh` failure (story 5 of 11 fails to create), **stop and report exactly what filed and what didn't** — don't blind-retry; let the user resume or clean up.

Single bug/feature drafting and revise mode are unchanged — they keep their Step 6 human gate. Only the Epic batch goes hands-off.

### Story body shape

The first line of every Story body is the Epic backlink, then the standard Story sections:

```
**Epic:** #<epic-#> — <Epic title>
```

This matches the `.github/ISSUE_TEMPLATE/story.md` shape so the link is present whether the issue is filed via the skill or the GitHub web UI.

---

## Step 3: Gather missing context

Ask only what's needed. Be surgical — the user is mid-flow on something else, and a 10-question interrogation is worse than a slightly thinner issue.

**For bugs, the minimum viable issue needs:** what happened, what was expected, and steps to reproduce (or at minimum, what they were doing when it occurred). If they didn't mention environment and it could plausibly matter (browser bug, OS-specific, version-specific), ask.

**For incomplete features, you need:** what currently works, what's missing, and what "done" looks like. The user often has all this in their head — your job is to get it onto the page.

**For new features, you need:** the user/persona, the goal, and the underlying motivation (the "so that" in a user story). Acceptance criteria are great but can be a stretch goal — better to file a thinner issue than to badger the user.

**For questions, you need:** the question itself, the target audience(s), and enough context that the audience can answer it cold — plus the references (docs, code, epics, issues) that ground it, and what the answer unblocks. Surface any **hard external constraints** that bound the answer — regulation, legal/compliance, insurance, contracts/SLAs, third-party-platform limits — each paired with the force that fixes it, so the audience sees what's already off the table and *why* rather than inferring it from the references (the Question template's `## Constraints` section). If the question came from a tracked-questions list, get its external id (e.g. `PRD-OQ-06b`). When more than one audience is named, confirm what each audience is being asked — a business stakeholder and an architect usually need the same question framed differently, not two unrelated questions.

**Critical:** Never invent reproduction steps, error messages, or behavior the user didn't describe. If you don't know, say "[to be filled in]" or ask. A vague-but-honest issue is better than a confidently-wrong one.

## Step 3.5: Resolve open questions detected in the source

Runs only when Step 2's "Detecting open questions" found ≥1 open OQ that gates this **build** issue. **Match first** — before proposing anything, search the tracker for an existing companion per [`../_shared/open-question-detection.md`](../_shared/open-question-detection.md) (proposing a file before checking is how you offer to duplicate a question that already exists). Then, for each gating OQ, get the user's disposition — one `AskUserQuestion` card per OQ (per [`../_shared/asking-the-user.md`](../_shared/asking-the-user.md); `header` e.g. `"OQ <id>"`), the `question` field naming what the OQ gates and each option's consequence. The three dispositions are the closed set in [`../_shared/open-question-links.md`](../_shared/open-question-links.md):

- **Scope it out** *(default — list first)* — build only the decided scope; the gated part goes to `## Out of scope` (naming the OQ) and is re-filed as a follow-up once the question is answered. Nothing undecided lands in this issue's Definition of done.
- **Keep in-scope (blocked)** — keep the gated part in the DoD; the build issue is set natively `blocked by` the companion question, which **holds the resolver and evaluator** until it's answered (warn the user of that).
- **Build on a provisional default** — build now on a named provisional choice; record `default:` + `retires-when:` so the decision stays visible and the planner carries it as a watchpoint.

**Companion question — reuse, file, or defer to the sweep:**
- **A match exists** → default to **reusing** it: link it as the companion (and, for `in-scope (blocked)`, native-block on it). Reach for `AskUserQuestion` only to resolve a genuine ambiguity — **Reuse #N** (default) / **File a new one** (when #N isn't actually the same OQ). A reused question is **not re-filed** — you only add the cross-links (its `Related to #<this issue>` and this issue's `blocked by` / `## Open questions` reference to it).
- **No match** → offer to **file** a companion now (a normal `question`-type draft: the body / audience-label / `## Tracked in` schema is [`../_shared/question-issue.md`](../_shared/question-issue.md); filing reuses this skill's Step 5 review, Step 6 gate, paste-ready snippet, and terminal handoff, with `## Why this matters` naming the gated scope). Or **defer to the sweep** — tell the user `/github-pipeline:open-questions` will reconcile it (and the rest of the project) at once. Either way, still record the OQ at Step 4; never leave it silently frozen.

**`in-scope (blocked)` requires a target to block on.** A native `blocked by` can't point at a question that doesn't exist, so this disposition needs a companion question — a freshly filed one or a de-dup'd existing one. If the user picks `in-scope (blocked)` but declines to file (and none exists), don't leave a dangling block: either fall back to **scoped-out** (the default — the honest "not decided, so out of this issue" choice) or keep it in-scope as a **prose-only** blocker (`question: (not filed)`, no native `blocked by`) and tell the user the resolver/evaluator won't hard-gate it until a question exists. Never emit `blocked_by=` with no `#N`.

Record every disposition in the build issue's `## Open questions` section at Step 4.

## Step 4: Draft the issue

### Title conventions

Titles should be specific and action-oriented. They show up in lists where context is scarce.

- Bug: `[Bug] <component>: <what's wrong>` — e.g., `[Bug] Login: button misaligned on mobile Safari`
- Incomplete: `[Incomplete] <component>: <what's missing>` — e.g., `[Incomplete] Export: CSV export missing for archived items`
- Feature: `<verb> <object>` — e.g., `Add CSV export for user data`
- Epic: `Epic: <theme>` — e.g., `Epic: Chat & session UX polish`
- Story: `<verb> <object>` — same convention as Feature; the `story` label conveys type, no prefix needed.
- Question: `<tracker-id> — <question topic>` when a tracker id exists — e.g. `PRD-OQ-06b — Which billing model for v1?`; otherwise just the question topic phrased as a question. The id in the title makes the issue findable by the tracker reference both ways.

Drop the `[Bug]`/`[Incomplete]`/`[Question]` prefix if the repo uses labels for type (most do). Prefixes are a fallback for repos without good labeling.

### Built-in templates (use only if repo has no template)

These are a fallback — prefer the repo's own issue template when one exists (Step 2). **See [`references/issue-templates.md`](references/issue-templates.md)** for the built-in Bug, Incomplete-feature, New-feature (user-story), Epic, Story, and Question body templates, plus the rule for when to include an `## Out of scope` section (omit by default; only on an explicit user exclusion, a genuine scope ambiguity, or an open-question `scoped-out` disposition).

### Recording open questions (when Step 3.5 produced dispositions)

Write the build issue's `## Open questions` section per the schema in [`../_shared/open-question-links.md`](../_shared/open-question-links.md) — one entry per gating OQ with its disposition, companion `question: #N` (or `(not filed)`), and audience. Then, per disposition: for each **scoped-out** OQ, also write the matching `## Out of scope` line naming the OQ (that keeps the gated part out of the DoD); for each **in-scope (blocked)** OQ **with a filed companion**, keep the gated criterion in the DoD and set the native `blocked by` to the companion question (via `PERSIST_CREATE blocked_by=` at file time — Step 7) — an in-scope-blocked OQ recorded `question: (not filed)` is prose-only: keep the criterion but set **no** native block (never a `blocked_by=` with no `#N`); for each **provisional-default** OQ, build the decided-plus-provisional scope into the DoD and record `default:` + `retires-when:` in the entry. **For every filed companion `question: #N`, also add a `Related to #N` line to `## Related issues`** — the human/GitHub cross-link, and the always-present fallback that carries the relationship when native dependencies aren't available (per the contract's capability-degradation rule). Don't invent OQs the source didn't mark — the same anti-fabrication bar the rest of the skill applies.

### Labels and priority

Apply labels in this order of preference:

1. **Type label** — `bug`, `enhancement`, `incomplete`, `epic`, `story`, `question` (or repo equivalents like `kind/bug`). In repos that don't already have `epic`, `story`, or `question` labels, suggest creating them at the end rather than inventing ad-hoc labels.
2. **Priority** — based on user's tone and impact. If unclear, ask or default to medium.
   - `priority:high` / `P1` — blocks the user, affects many users, data loss/corruption, security
   - `priority:medium` / `P2` — noticeable but workable
   - `priority:low` / `P3` — minor, polish, nice-to-have
3. **Component/area** — only if the repo uses these and you can confidently pick one

Don't over-label. Three labels max unless the user asks for more.

### Audience labels (questions only)

The audience-label rule — one `audience:*` label per audience (named or clearly implicated), filterable, off the three-label cap; priority omitted unless the question is blocking; and the offer-to-create-a-missing-`audience:*`-label step at the Step 6 gate — is [`../_shared/question-issue.md`](../_shared/question-issue.md) (single source of truth; don't restate). Apply it here at Step 4. The one drafter-specific placement: create each missing `audience:*` label in the main loop **right before filing** (the same place Step 2 runs `gh label list` inline, not through `github-ops`).

## Step 5: Sub-agent review loop

Before showing the draft to the user, hand it to an isolated review sub-agent. The sub-agent runs **without the conversation history** — it sees only the issue's own content, the repo, and the project docs. If it can't make sense of the issue using just those inputs, neither will a teammate reading the issue six months from now. That's the test the loop is designed to apply.

This step runs for both new drafts and revisions of existing issues. Don't skip it. The cost of one read-only sub-agent invocation is small compared to the cost of a confidently-wrong issue surfaced to the team.

### Why a sub-agent (not just a self-check)

You drafted the issue while holding informal feedback, prior turns, the user's tone, the original problem description — context that won't appear in the filed body. From that vantage point you can't tell whether the body stands on its own. The sub-agent is the cheap way to simulate a fresh reader. Resist the urge to "save a turn" by skipping it; self-review under load tends to be charitable in exactly the wrong direction.

### Invocation contract

Invoke an `Explore` sub-agent with the prompt template at `references/issue-reviewer-prompt.md`. Inline the draft into the prompt and pass the structural inputs:

```
Agent({
  subagent_type: "Explore",
  description: "Review GitHub issue draft for coherence",
  prompt: <contents of references/issue-reviewer-prompt.md
           with placeholders filled: draft, mode, repo_root,
           open_question_markers, dimensions, related_drafts>
})
```

The sub-agent receives:

- **Draft** — title, body, labels, priority, type (`bug` | `incomplete` | `feature` | `epic` | `story` | `question`).
- **Mode** — `draft` (no number yet), `revise <N>` (existing filed issue — sub-agent fetches the live state via `gh issue view` and walks the comment thread itself), or `split` (Epic split loop — no story bodies yet; sub-agent runs dimensions 5 and 7 adversarially over the scope-level split and greps to ground every claim).
- **Repo root** — absolute path so the sub-agent can read `docs/`, `CLAUDE.md`, and grep the source tree.
- **Open-question markers** — the `<!-- drafter-open-question-markers -->` block contents (or the heuristic-cue instruction, or empty) from Step 2's detection, so the dimension-1 frozen-undecided check can tell an open decision from a settled one.
- **Dimensions** — the explicit list of checks to run (see below). Pass only the dimensions that apply for the current type/mode.
- **Related drafts** — for an Epic, pass the sibling stories so the sub-agent can reason across them for dimensions 5 and 7. In `split` mode pass each story's title + one-line scope (files / layer / test surface); for the Step E2 body re-confirm pass each story's title + full body.

The sub-agent does **not** receive: the conversation history, the user's original informal feedback, your draft notes, the user's tone or prior turns. The isolation property is what makes the review meaningful — leaking conversation context defeats the purpose.

### Review dimensions

Six dimensions. Each yields zero or more findings, each finding carries severity + concrete evidence.

| # | Dimension | Checks | Example finding |
|---|---|---|---|
| 1 | **Doc coherence** | Cross-reference body against `docs/prd.md`, `docs/architecture.md`, `docs/constitution.md`, `CLAUDE.md`. Four patterns: contradicts / extends / gap, plus **frozen-undecided** (build types only) — the body states as decided something the source still marks open, with no `## Open questions` entry dispositioning it. | `Body proposes 'allow editing submitted entries' — PRD §4 says entries are immutable after submit. Either body or PRD must move. Recommend adding a 'PRD impact' note flagging the contradiction.` |
| 2 | **Codebase coherence** | grep/find every API, file, type, component, behavior named in the body. Confirm presence in current code. | `Body references 'OldService.foo()'; no such symbol in current codebase (closest match: NewService.foo at app/services/new_service.rb:42). Likely renamed during refactor — update reference or describe the renamed surface.` |
| 3 | **Internal coherence** | Title matches body claim; acceptance criteria support the stated goal; "what's missing" is actually missing per the code; Story Epic backlink is correctly formatted; Out-of-scope doesn't contradict in-scope; `## Open questions` entries are consistent (scoped-out ↔ `## Out of scope`; provisional-default carries default+retires-when; `question: #N` resolves). | `Acceptance criterion #3 ('exports as PDF') doesn't appear in the user story or background — looks orphaned. Either justify in body or drop.` |
| 4 | **Latest-decisions** *(revise mode only)* | Walk the comment thread; identify the most recent substantive direction-setting comment; compare body to that direction. | `Comment by @maintainer on 2026-04-12 settles on 'approach B' but body still describes approach A. Revise body toward B; cite the comment.` |
| 5 | **Story ordering** *(Epic mode — split scopes or filed bodies)* | Build a dependency graph: for each story, infer dependencies from the files/APIs/types it references and what it claims to deliver. Compare topological order to the Epic's `## Stories` listed order. | `Story 3 'Add export-to-CSV button' depends on the export service introduced by Story 5 'Build export service'. Listed order has 3 before 5; topological order is 5 → 3. Recommend swapping.` |
| 6 | **Completeness** *(primarily draft mode)* | Required template sections present? User story for features? Definition of done for stories? Reproduction for bugs? | `Bug template requires 'Steps to reproduce'; section is empty. Either fill in (ask the user) or include a [to be filled in] placeholder so the gap is visible at triage.` |
| 7 | **Story sizing / over-split** *(Epic mode — adversarial)* | Apply the three coalescing signals across the proposed split: shared verification surface, sequential-with-no-standalone-value, same-files/layer+thin. Flag slices that should **merge** — and, via the guardrail, slices wrongly **merged** that should split. Ground every surface-overlap claim by grepping the codebase. | `Story 2 'Add pill view' and Story 3 'Add history view' have no inter-dependency, are both mounted only by Story 4, and share one snapshot suite (`…/Snapshots/Floating*`) — same verification surface, signal 1. Recommend merging into one 'Add the two floating views' story.` |

Pass the relevant dimensions per type/mode. Bugs run 1, 2, 3, 6 (and 4 if revising). Features run 1, 2, 3, 6 (and 4 if revising). Questions run **1, 3, 6** — and **2 only if the body cites code, APIs, or file paths** (most business questions cite none, so passing 2 there only invites empty findings); dimension 3 carries the question's quality bar (answerable + phrased for the labeled audience), and 5/7 never apply. For an Epic, the split loop (Step E1) runs **5 and 7 only** on the scope-level split *before* bodies exist; the per-Story body review (Step E2) then runs 1, 2, 3, 6 on each body and **re-confirms 5 and 7** across the set. Stories run 1, 2, 3, 6 (and 4 if revising); sizing and ordering (5, 7) apply to the parent Epic's split, not the individual Story. In revise mode, an Epic re-audit can also re-run 5 and 7 against the current story set.

### Severity and evidence

Each finding carries one of three severities:

- **Blocker** — the issue is concretely wrong: referenced API doesn't exist; PRD directly contradicts; story order makes a story unimplementable until a later story ships. Must be addressed before filing.
- **Suggestion** — would meaningfully improve clarity or alignment. Address by default; the user may defer with reason.
- **Nit** — small polish (typo, slight rewording for searchability). Apply silently or skip; never block on these.

**Evidence is mandatory.** Every finding must cite at least one of:

- A specific line/section of the issue body (quote it).
- A specific file path + line range or section in the docs/codebase.
- A specific comment by author + date in the issue thread (revise mode).

Findings without evidence are **dropped** before iterating. "Seems unclear" without a quote and an alternative wording does not pass the bar. This anti-fabrication rule is the same one the rest of the skill applies to drafting ("Never invent reproduction steps, error messages, or behavior the user didn't describe") — extend it to the reviewer.

### Loop control

```
draft = orchestrator.initial_draft
prev_findings = []
for pass in 1..3:
  findings = sub_agent.review(draft, mode, repo_root, dimensions)
  drop_findings_without_evidence(findings)
  if findings is empty:
    exit_clean()
    break
  if same_finding_repeated_with_no_progress(findings, prev_findings):
    exit_circular(draft, findings)
    break
  draft = orchestrator.apply(findings, draft)   # blockers always; suggestions by default; nits silently or skipped
  prev_findings = findings
else:
  exit_cap_reached(draft, findings)

show_to_user(draft, unresolved_findings_if_any)
```

Three exit conditions:

- **Clean** — pass returns no findings (after evidence-filtering). Show only the draft.
- **Cap reached** — three passes done, findings still remain. Show the draft AND the remaining findings; let the user decide whether to file as-is, fix manually, or push back on the reviewer.
- **Circular** — the same finding (matched by dimension + evidence-quote) appears in two consecutive passes without measurable progress. Stop. The reviewer might be wrong, or the orchestrator's revision might be missing something the user needs to clarify. Surface both the latest draft and the recurring finding to the user; don't burn the third pass guessing.

The cap and the circular guard exist for the same reason: don't iterate forever on a finding that's either wrong, unactionable, or needs human judgment. Fold what you can, surface what you can't.

### What the user sees at the confirmation gate

Existing flow (Step 6) shows the draft. New behavior:

- **Clean exit** — show the draft. Optional one-line note: `(reviewed in N pass(es); no issues)`. Don't make a meal of it.
- **Cap or circular exit** — show the draft AND a "Review notes" block listing each unresolved finding with severity, evidence, and the recommended remediation. The user can choose to file anyway, fix the body manually, or tell you to take another pass with adjusted guidance.

Keep the cost low when the loop is clean. Surface real disagreements when they exist. Don't pad the user-visible output with reviewer noise.

## Step 6: Show the draft and confirm

Present the full draft like this:

```
Here's the draft:

Title: <title>
Labels: <label1>, <label2>
Priority: <priority>

---
<body>
---

Should I file this, or want to tweak anything first?
```

Then ask via `AskUserQuestion` (header "File issue?"): **File it** — create the issue now via `gh issue create`; **Keep iterating** — hold off and refine the draft further. Treat anything other than an explicit "File it" — silence, a follow-up question, a tweak request, or a custom "Other" answer — as keep-iterating; never file without that explicit go-ahead.

**Before you ask the question, stage the approved body to disk.** Write the exact body you just rendered between the `---` fences to `/tmp/gh-drafter-<slug>/draft-final.md` (`<slug>` = a short identifier of your choosing — Epic number, issue title slug, anything stable for this run). Keep the path in mind as `draft_path`. The staged file *is* the body — `github-ops` reads its bytes through the bundled `gh-persist.sh` script and posts them directly to `gh issue create --body-file`. The body never gets re-serialized into the sub-agent's prompt, so prompt compaction can't abbreviate it to `<see above>` and the in-agent Write/Bash race that filed empty bodies on #626/#627 has nothing left to race on. Do the same for every Story body in an Epic batch, one file per story.

## Step 7: File the issue

Once the user has approved at step 6, hand the create to `github-ops` by passing the staged path — not by re-inlining the body. `github-ops` shells out to `${CLAUDE_PLUGIN_ROOT}/scripts/gh-persist.sh create`, whose very first action is `test -s <body_path>`; if your staging step succeeded, the file is non-empty and the script posts those exact bytes. If you forgot to stage or the file is somehow empty, `github-ops` returns `DECISION_NEEDED: PERSIST_CREATE called with empty body file at <path>` and posts nothing — re-write `draft_path` and re-dispatch with the same path.

> `PERSIST_CREATE(repo=<owner/repo>, title=<approved title>, body_path=<draft_path>, labels=[<label>, …])`

It returns the new issue URL, the `#NN`, plus `body_bytes` and `body_sha256` for the bytes that posted. Share the URL with the user. You can cross-check `body_sha256` against `shasum -a 256 <draft_path>` if you want a byte-for-byte loop close; the script computes the same hash on the file the caller wrote, so a mismatch points at a corrupted scratch dir, not at github-ops. If `gh` errors out (auth, label doesn't exist, etc.), `github-ops` reports the exact error rather than retrying with different flags; relay it and adjust.

### Filing a build issue that has open questions (two-phase)

When Step 3.5 produced companion questions and/or an `in-scope (blocked)` disposition, file in this order so no dispatch forward-references an issue that doesn't exist yet (mirrors the Epic "file, then patch" pattern below):

1. **File any NEW companion `question` issues first**, collecting each `#N` — a companion that Step 3.5's de-dup reused already has its `#N`, so don't re-file it (just carry it into step 2's references). Each new one is a normal question create (its own staged body, audience labels, snippet, terminal handoff).
2. **File the build issue**, with its `## Open questions` section already naming those `#N`, and pass native `blocked by` for each `in-scope (blocked)` OQ **that has a filed companion** plus any user-stated `Blocked by #N`:
   > `PERSIST_CREATE(repo=<owner/repo>, title=<title>, body_path=<draft_path>, labels=[…], blocked_by=[<companion #N for each in-scope-blocked OQ with a filed companion>, <any user-stated blocker>])`
   `github-ops` capability-gates the native deps — on a repo/gh without the feature it returns a `DEPS_UNSUPPORTED:` notice and files without them; the prose `## Open questions` / `## Related issues` links remain, so the dependency is still recorded. `scoped-out`, `provisional-default`, and prose-only `in-scope (blocked)` (`question: (not filed)`) OQs set **no** native block (only a filed-companion in-scope-blocked OQ contributes a `#N` — never a `blocked_by` element with no number).
3. **Patch each companion's `## Tracked in`** to add the now-known build issue `#` — stage the updated companion body and `PERSIST_BODY(mode=replace, …)` per companion (same staged-file discipline). A dep-only change (never a body change) uses `PERSIST_LINK` instead.

### After filing a question

A question exists to be referenced from wherever it was raised (a PRD's Open Questions list, a design doc, a meeting note), so make the `#NN` easy to wire back in. Call out the bare `#NN` and the URL, then emit a **paste-ready snippet** for the source doc — the skill prints it, the user pastes it (it does not edit the doc):

```
- PRD-OQ-06b: Which billing model for v1? — tracked in #210
```

Match the snippet's shape to the doc's existing list style when you've read the doc; if no tracker id exists, drop the `PRD-OQ-06b:` prefix. This is the only post-file output for a question — then go straight to the terminal handoff (Step 8).

### Filing an Epic with child stories

The Epic flow files the whole set in one batch once Steps E1 and E2 come back clean (see "One-shot filing flow") — there's no per-story confirmation gate; a clean pass through the split loop and the body review is the go-ahead. Each write still goes through `github-ops`, and the same staged-file discipline from Step 7 applies to every body: at the end of Step E2, stage the Epic body to `/tmp/gh-drafter-<epic-slug>/epic.md` and each Story body to `/tmp/gh-drafter-<epic-slug>/story-<NN-or-index>.md` before any `PERSIST_CREATE` fires. Pass each staged path into `body_path=` on the dispatch; `github-ops` reads those bytes through `gh-persist.sh` and posts them directly. An Epic batch crosses the sub-agent boundary once per story plus once for the Epic itself; with `body_path=` each of those dispatches carries only the path, so the body bytes never get a chance to be dropped, abbreviated, or substituted under context pressure. (The two empty-body issues on the #512 batch — #626 and #627 — happened under the old inline-body contract; this is the surface the path-based contract closes.)

For each Story body, embed the Epic backlink directly in the staged file (write `**Epic:** #<epic-#> — <Epic title>\n\n` at the top of `story-<i>.md` when you stage it, not at dispatch time) — the dispatch carries only the path, so any prefix must already be on disk.

1. Create the Epic (placeholder bullets in `## Stories` for now):
   > `PERSIST_CREATE(repo=<owner/repo>, title=<epic title>, body_path=/tmp/gh-drafter-<epic-slug>/epic.md, labels=["epic"])`
2. For each Story in dependency order, file it with the Epic backlink already written into the staged file, collecting each `#NN`:
   > `PERSIST_CREATE(repo=<owner/repo>, title=<story title>, body_path=/tmp/gh-drafter-<epic-slug>/story-<i>.md, labels=["story"])`
3. Patch the Epic body — swap the placeholder bullets for `- [ ] #NN — <Story title>` links — write the patched body to `/tmp/gh-drafter-<epic-slug>/epic-patched.md`, then:
   > `PERSIST_BODY(issue=<epic-#>, repo=<owner/repo>, mode=replace, body_path=/tmp/gh-drafter-<epic-slug>/epic-patched.md)`

If any `PERSIST_CREATE` fails mid-batch, stop and report exactly which issues were created and which weren't — don't retry blindly. The user resumes from the gap or cleans up. If `github-ops` returns the empty-body `DECISION_NEEDED` on any dispatch in the batch (`EMPTY_BODY_FILE: <path>`), the staged file is missing or empty — re-write it and re-dispatch with the same path; don't skip the story.

## Step 8: Handoff

Every clean run of this skill ends with a single `## Handoff` block — the schema, omission rules, and state-marker vocabulary live in [`../_shared/handoff-format.md`](../_shared/handoff-format.md). The handoff is the only bridge between this session and the next: the user will copy the fenced command into a fresh Claude Code session to continue. Don't skip it on a clean exit; don't add anything after it.

Pull the snapshot from data you already have — the `PERSIST_CREATE` result(s) carry the issue/Epic/story numbers and titles; `plan: ✗` is correct because the drafter never authors plans. The `Why:` line is yours to write — describe what the next session will do (don't repeat the schema).

For a **question**, the handoff is **terminal** (it's answered by a human, not a downstream skill): omit the `research:`/`plan:` markers — they don't apply — add an `**Audience:**` line listing the `audience:*` labels, and replace the fenced command with `(terminal — no follow-up skill)`. The `Why:` explains it awaits a human answer and what to do once it lands. See the question rendering in `references/handoff-renderings.md`.

For a **build issue drafted with open questions**, add a free-form `**Open questions:**` line (not a state marker — see handoff-format.md) listing the companion `question` issues and a short disposition tally covering every OQ (e.g. `2 scoped out, 1 blocked-by, 1 provisional` — include a prose-only in-scope-blocked OQ in the count even though it set no native block), and note in the `Why:` that the planner plans only the decided scope. See the "Single issue filed with open questions" rendering in `references/handoff-renderings.md`.

**Before composing the handoff, `Read references/handoff-renderings.md`** — it holds the worked `## Handoff` shapes the drafter emits: single issue filed (forward to the planner), Epic batch filed (forward to the planner), and revise-mode (forward to author a plan, stale-refresh, or terminal — per whether a plan exists and whether the revise was material). It's a progressively-disclosed reference — not auto-loaded with this skill — so the forced Read is what guarantees the shapes are in your working context before you emit; without it the handoff may be written from memory and drift from the closed-set shapes. Each carries the closed-set state-marker vocabulary from [`../_shared/handoff-format.md`](../_shared/handoff-format.md); fill the snapshot from the data Step 8 lists above.

## Handling edge cases

**User describes multiple things at once.** ("The export is broken AND we should add a dark mode toggle.") File these as separate issues. Confirm with the user that you're splitting them.

**User isn't in a repo directory.** `gh repo view` will fail. Ask which repo to file against and use `--repo owner/name` on the create command.

**User wants to file against a different repo than the cwd.** Honor that — pass `--repo` explicitly.

**Repo has issue templates but they don't fit.** Use the closest one and adapt. If genuinely none fits (e.g., they only have a "bug" template and the user wants to file a feature), use the built-in feature template.

**The feedback is too thin to file a useful issue.** Push back gently: "This is a bit thin — do you have a [reproduction step / persona / what 'done' looks like]? Otherwise we can file a stub and flesh it out later." Filing stubs is fine if the user prefers; just be honest about what's missing in the body.

**Revise mode: the referenced issue is closed.** Surface it before doing any work — state the closure ("#N is closed, closed by PR #M on date X") and ask via `AskUserQuestion` (header "Closed issue"): **Revise as-is** — edit the closed issue in place without reopening; **Reopen first** — reopen the issue, then revise it; **File follow-up** — leave the closed issue alone and file a new follow-up issue instead. Closed issues sometimes get reopened intentionally; sometimes the user meant a different number. Ask, don't guess.

**Revise mode: the referenced issue doesn't exist or you can't access it.** `gh` errors out with 404 / no permissions. Report the exact error and ask the user to check the number/repo. Don't fall back to drafting a new issue silently.

**Review loop keeps surfacing the same finding across passes.** That's the circular exit. The reviewer might be wrong, or the orchestrator's revision might be missing something the user needs to clarify. Surface the latest draft + the recurring finding to the user; don't burn the third pass guessing. Recovery: state the recurring finding ("the reviewer keeps saying X") and ask via `AskUserQuestion` (header "Review loop"): **It's real, keep fixing** — the finding is valid, take another revision pass at it; **Override and file** — the reviewer is wrong, file the draft as-is despite the finding.

## Why this matters

Issues are a primary artifact of product development. A vague issue costs the team 10x more in re-triage time than the 30 seconds saved when filing it. The skill's goal isn't speed — it's making sure each filed issue has enough context that anyone on the team (including future-you) can pick it up cold.
