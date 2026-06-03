---
name: github-issue-drafter
description: Drafts well-structured GitHub issues from informal developer feedback and files them via the `gh` CLI. Use this skill whenever the user describes a bug they hit, an incomplete or half-built feature they noticed, or a new feature idea — and wants it captured as a GitHub issue. Trigger this even when the user does not explicitly say "make an issue" — phrases like "I should track this," "let's file this," "we need to remember to fix X," "log this for later," or simply describing a problem in a repo context all qualify. Also use this skill to **revise an existing issue** when the user references one by number/URL with revision intent — phrases like "revise #N," "update issue #N," "improve #N," "does #N still match the docs?", or "rewrite the description of #N." Works best when the user is inside a git repository directory. Uses repo issue templates and labels if they exist, otherwise applies a consistent built-in format. Reads the project PRD (if one exists at `docs/prd.md` or similar) to ground feature framing and surface tensions between feedback and spec. Every drafted or revised issue is automatically validated by an isolated review sub-agent that checks the issue against the project's PRD, architecture, constitution, and current codebase before the user sees the final draft.
---

# GitHub Issue Drafter

Turn informal developer feedback into well-structured GitHub issues. The user is mid-development on a product and notices things — bugs, gaps, ideas. Your job is to capture those cleanly so future-them (or their team) has enough context to act.

This skill is the first stage of a pipeline: it files the issue; `github-issue-planner` later researches and attaches a verified implementation plan (stored as a comment, not in the body); `github-issue-resolver` then builds it. The practical consequence for **revise mode** is that an issue you drafted may have a plan comment attached after the fact — leave that comment alone, preserve its body pointer, and flag when a body revision may have invalidated it (see Revise mode).

### Asking the user a decision

When you need a decision from the user — an approval gate, a choice between named
paths, or a confirmation before a GitHub write — ask it through the `AskUserQuestion`
tool, not as freeform prose. The tool renders the same multiple-choice card every
time, so the user pattern-matches the decision at a glance instead of re-parsing a
differently-worded question on each run.

Shape every ask the same way:
- One decision per question. `header` ≤ 12 chars (e.g. "Post plan", "Merge mode").
  The `question` field carries the full prose you'd otherwise have typed.
- 2–4 options. Each `label` is the action in imperative form ("Post it", "Squash",
  "Approve"); each `description` says what that choice does and its consequence.
- The tool always appends an "Other" free-text choice, so don't pad to four options
  with a catch-all — leave room for the user to type a custom answer.
- `multiSelect: true` only when the choices genuinely combine (rare here).
- Ask once, act on the answer. Don't re-state the same gate in prose afterwards.

When the candidate paths aren't fixed (e.g. "which of these issues did you mean?"),
generate the options dynamically from what you found. When the answer is inherently
open-ended (e.g. "paste any external doc URLs"), a prose ask is still fine — don't
force it into options.

`AskUserQuestion` is not available inside a sub-agent spawned via the `Agent` tool.
Any gate that arises during sub-agent work must be surfaced by the sub-agent
returning a structured "decision needed" signal to this main loop, which asks the
user and re-dispatches with the answer. Never tell a sub-agent to call
`AskUserQuestion` itself.

### Delegating mechanical work to `github-ops`

The judgment in this skill — classification, PRD-tension calls, drafting, applying
review findings — is what's worth a high-effort model. The judgment-free I/O is
not: fetching an issue + thread for revise mode, reading referenced issues,
checking templates/labels, and the `gh issue create` / `gh issue edit` writes.
Delegate that to the **`github-ops`** sub-agent (`subagent_type: "github-ops"`,
Sonnet + medium effort — spawn with **no `model` override**). It runs a named
operation and returns faithful structured results: `GATHER_ISSUE`,
`PERSIST_BODY`, `PERSIST_CREATE` — see `.claude/agents/github-ops.md`. It
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

1. **Classify** the feedback: bug, incomplete feature, or new feature.
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

Same loop as for drafts (see "Sub-agent review loop" below). Feed the sub-agent the existing title + body + labels + the type (bug | incomplete | feature | epic | story). Mode is `revise <N>` — the sub-agent fetches the live state for itself and walks the comment thread under the latest-decisions dimension.

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

**One nuance worth surfacing to the user:** if the user said "this may be resolved by #21," that's a hint they're unsure whether to file at all. It's worth a quick "I'll file this with a note that #21 might already cover it — or do you want to wait and check #21 first?" Most users will say file it anyway (cheap to close as duplicate later), but giving them the choice respects their time.

## Epics and child stories

### When Epic applies

An Epic is for work where each child is **independently shippable** — a separate PR, separate review, separate merge. Don't use Epic just because a feature has several acceptance criteria; use it when those criteria represent distinct deliverables a developer could pick up one at a time. If in doubt, ask the user.

### Sizing stories: coalesce thin slices

"Independently shippable" is a ceiling, not a target. It tells you when work *can* be split; it says nothing about when it *shouldn't* be. Splitting has a cost the issue body never shows: every story a developer picks up pays a fixed tax — a fresh worktree and simulator, a static-check baseline, a cold build, a targeted test run, and a full review-loop round-trip — before any of its actual work counts. A 40-line story and a 400-line story pay almost the same tax. Slice too thin and that tax dominates: ten trivial stories can cost more wall-clock in setup, testing, and review than three substantial ones that deliver the same thing.

So aim for the **coarsest** slicing that still keeps each story independently shippable. After you have a candidate story list, make a coalescing pass over adjacent slices and **merge** a pair (or cluster) when any of these fire:

1. **Shared verification surface** — the slices would re-run the *same* expensive verification: the same build, the same UI-test target, the same snapshot-golden set. Splitting them means paying that verification twice for one logical change. (E.g. two new views mounted by the same container that share one snapshot suite — review them together, with both visible in context.)
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

**Critical:** Never invent reproduction steps, error messages, or behavior the user didn't describe. If you don't know, say "[to be filled in]" or ask. A vague-but-honest issue is better than a confidently-wrong one.

## Step 4: Draft the issue

### Title conventions

Titles should be specific and action-oriented. They show up in lists where context is scarce.

- Bug: `[Bug] <component>: <what's wrong>` — e.g., `[Bug] Login: button misaligned on mobile Safari`
- Incomplete: `[Incomplete] <component>: <what's missing>` — e.g., `[Incomplete] Export: CSV export missing for archived items`
- Feature: `<verb> <object>` — e.g., `Add CSV export for user data`
- Epic: `Epic: <theme>` — e.g., `Epic: Chat & session UX polish`
- Story: `<verb> <object>` — same convention as Feature; the `story` label conveys type, no prefix needed.

Drop the `[Bug]`/`[Incomplete]` prefix if the repo uses labels for type (most do). Prefixes are a fallback for repos without good labeling.

### Built-in templates (use only if repo has no template)

**Bug template:**

```markdown
## Description
<one-paragraph summary of the bug>

## Steps to reproduce
1. <step>
2. <step>
3. <step>

## Expected behavior
<what should happen>

## Actual behavior
<what actually happens, including any error messages>

## Environment
- <OS / browser / version / etc., if relevant>

## Related issues
<only if user referenced other issues — see "Detecting related issues" above. Omit section if none.>

## Additional context
<screenshots, logs, anything else — omit section if none>
```

**Incomplete feature template:**

```markdown
## What exists today
<what currently works>

## What's missing
<the specific gap>

## Definition of done
- [ ] <criterion>
- [ ] <criterion>

## Context
<why this was left incomplete, if known>

## Related issues
<only if user referenced other issues. Omit section if none.>
```

**New feature template (user story):**

```markdown
## User story
As a **<persona>**, I want **<capability>** so that **<benefit>**.

## Background
<why this matters — the underlying motivation>

## Acceptance criteria
- [ ] <criterion>
- [ ] <criterion>

## Related issues
<only if user referenced other issues. Omit section if none.>
```

**Epic template:**

```markdown
## Goal
<one paragraph: what this epic delivers, what problem it solves>

## Background
<why now — what prompted this work; reference PRD/architecture sections where relevant>

## Stories
- [ ] <Story 1 title>
- [ ] <Story 2 title>

## Definition of done
- [ ] All stories above are closed
- [ ] <any epic-level acceptance bar, e.g. "5 UI flows green in CI">

## Related issues
<only if user referenced other issues. Omit section if none.>

## PRD impact
<only if applicable. Omit otherwise.>
```

**Story template:**

```markdown
**Epic:** #<epic-#> — <Epic title>

## What exists today
<what currently works in this area, and what limitation prompted this story>

## What's missing
<the specific gap this story closes; reference architecture/PRD sections where relevant>

## Definition of done
- [ ] <criterion>
- [ ] <criterion>

## Context
<optional — dependencies, constraints, why this was deferred>

## Related issues
<only if user referenced other issues. Omit section if none.>
```

**About the "Out of scope" section:** Omit it by default. Only include it when one of these is true:

1. **The user explicitly excluded something** — e.g., "but I don't want to deal with X right now," "let's not bother with Y." Capture what they said, don't extrapolate.
2. **The title or capability is genuinely ambiguous about something a reader would reasonably assume is included.** For example, a feature titled "Add export to PDF" might reasonably make a reader assume bulk export is included; if it's not, that's worth calling out. The bar is high — only flag this when the ambiguity is real, not speculative.

Default to omitting. Acceptance criteria already define what's in scope; don't pad the issue with speculative exclusions. Inventing out-of-scope items the user never mentioned is a form of hallucination — resist it.

If you find yourself wanting to write "Out of scope" but can't point to either trigger above, leave it out.

### Labels and priority

Apply labels in this order of preference:

1. **Type label** — `bug`, `enhancement`, `incomplete`, `epic`, `story` (or repo equivalents like `kind/bug`). In repos that don't already have `epic` and `story` labels, suggest creating them at the end rather than inventing ad-hoc labels.
2. **Priority** — based on user's tone and impact. If unclear, ask or default to medium.
   - `priority:high` / `P1` — blocks the user, affects many users, data loss/corruption, security
   - `priority:medium` / `P2` — noticeable but workable
   - `priority:low` / `P3` — minor, polish, nice-to-have
3. **Component/area** — only if the repo uses these and you can confidently pick one

Don't over-label. Three labels max unless the user asks for more.

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
           dimensions, related_drafts>
})
```

The sub-agent receives:

- **Draft** — title, body, labels, priority, type (`bug` | `incomplete` | `feature` | `epic` | `story`).
- **Mode** — `draft` (no number yet), `revise <N>` (existing filed issue — sub-agent fetches the live state via `gh issue view` and walks the comment thread itself), or `split` (Epic split loop — no story bodies yet; sub-agent runs dimensions 5 and 7 adversarially over the scope-level split and greps to ground every claim).
- **Repo root** — absolute path so the sub-agent can read `docs/`, `CLAUDE.md`, and grep the source tree.
- **Dimensions** — the explicit list of checks to run (see below). Pass only the dimensions that apply for the current type/mode.
- **Related drafts** — for an Epic, pass the sibling stories so the sub-agent can reason across them for dimensions 5 and 7. In `split` mode pass each story's title + one-line scope (files / layer / test surface); for the Step E2 body re-confirm pass each story's title + full body.

The sub-agent does **not** receive: the conversation history, the user's original informal feedback, your draft notes, the user's tone or prior turns. The isolation property is what makes the review meaningful — leaking conversation context defeats the purpose.

### Review dimensions

Six dimensions. Each yields zero or more findings, each finding carries severity + concrete evidence.

| # | Dimension | Checks | Example finding |
|---|---|---|---|
| 1 | **Doc coherence** | Cross-reference body against `docs/prd.md`, `docs/architecture.md`, `docs/constitution.md`, `CLAUDE.md`. Same three patterns the existing skill already uses for the PRD: contradicts / extends / gap. | `Body proposes 'allow editing submitted entries' — PRD §4 says entries are immutable after submit. Either body or PRD must move. Recommend adding a 'PRD impact' note flagging the contradiction.` |
| 2 | **Codebase coherence** | grep/find every API, file, type, component, behavior named in the body. Confirm presence in current code. | `Body references 'OldService.foo()'; no such symbol in current codebase (closest match: NewService.foo at Services/NewService.swift:42). Likely renamed during refactor — update reference or describe the renamed surface.` |
| 3 | **Internal coherence** | Title matches body claim; acceptance criteria support the stated goal; "what's missing" is actually missing per the code; Story Epic backlink is correctly formatted; Out-of-scope doesn't contradict in-scope. | `Acceptance criterion #3 ('exports as PDF') doesn't appear in the user story or background — looks orphaned. Either justify in body or drop.` |
| 4 | **Latest-decisions** *(revise mode only)* | Walk the comment thread; identify the most recent substantive direction-setting comment; compare body to that direction. | `Comment by @maintainer on 2026-04-12 settles on 'approach B' but body still describes approach A. Revise body toward B; cite the comment.` |
| 5 | **Story ordering** *(Epic mode — split scopes or filed bodies)* | Build a dependency graph: for each story, infer dependencies from the files/APIs/types it references and what it claims to deliver. Compare topological order to the Epic's `## Stories` listed order. | `Story 3 'Add export-to-CSV button' depends on the export service introduced by Story 5 'Build export service'. Listed order has 3 before 5; topological order is 5 → 3. Recommend swapping.` |
| 6 | **Completeness** *(primarily draft mode)* | Required template sections present? User story for features? Definition of done for stories? Reproduction for bugs? | `Bug template requires 'Steps to reproduce'; section is empty. Either fill in (ask the user) or include a [to be filled in] placeholder so the gap is visible at triage.` |
| 7 | **Story sizing / over-split** *(Epic mode — adversarial)* | Apply the three coalescing signals across the proposed split: shared verification surface, sequential-with-no-standalone-value, same-files/layer+thin. Flag slices that should **merge** — and, via the guardrail, slices wrongly **merged** that should split. Ground every surface-overlap claim by grepping the codebase. | `Story 2 'Add pill view' and Story 3 'Add history view' have no inter-dependency, are both mounted only by Story 4, and share one snapshot suite (FoodJournalTests/Snapshots/ChatFloating*) — same verification surface, signal 1. Recommend merging into one 'Add the two floating views' story.` |

Pass the relevant dimensions per type/mode. Bugs run 1, 2, 3, 6 (and 4 if revising). Features run 1, 2, 3, 6 (and 4 if revising). For an Epic, the split loop (Step E1) runs **5 and 7 only** on the scope-level split *before* bodies exist; the per-Story body review (Step E2) then runs 1, 2, 3, 6 on each body and **re-confirms 5 and 7** across the set. Stories run 1, 2, 3, 6 (and 4 if revising); sizing and ordering (5, 7) apply to the parent Epic's split, not the individual Story. In revise mode, an Epic re-audit can also re-run 5 and 7 against the current story set.

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

Once the user has approved at step 6, hand the create to `github-ops` by passing the staged path — not by re-inlining the body. `github-ops` shells out to `.claude/agents/scripts/gh-persist.sh create`, whose very first action is `test -s <body_path>`; if your staging step succeeded, the file is non-empty and the script posts those exact bytes. If you forgot to stage or the file is somehow empty, `github-ops` returns `DECISION_NEEDED: PERSIST_CREATE called with empty body file at <path>` and posts nothing — re-write `draft_path` and re-dispatch with the same path.

> `PERSIST_CREATE(repo=<owner/repo>, title=<approved title>, body_path=<draft_path>, labels=[<label>, …])`

It returns the new issue URL, the `#NN`, plus `body_bytes` and `body_sha256` for the bytes that posted. Share the URL with the user. You can cross-check `body_sha256` against `shasum -a 256 <draft_path>` if you want a byte-for-byte loop close; the script computes the same hash on the file the caller wrote, so a mismatch points at a corrupted scratch dir, not at github-ops. If `gh` errors out (auth, label doesn't exist, etc.), `github-ops` reports the exact error rather than retrying with different flags; relay it and adjust.

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

### Renderings

**Single issue filed (the common case).** Forward to the planner.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✗

**Next:** plan the implementation in a fresh session.

    /github-issue-planner #142

**Why:** the planner will research the approach, ground it in docs + codebase precedent, post a verified `<!-- implementation-plan:v1 -->` comment, and lock the decisions the resolver needs.
```

**Epic batch filed.** Forward to the planner on the Epic — the planner's own fan-out plans each child story under its `## Stories` list and sequences them.

```
## Handoff

**Epic:** #150 — Chat & session UX polish · open · epic · plan: ✗
**Stories:** #151, #152, #153, #154, #155 (5 filed, dependency-ordered)

**Next:** plan the Epic in a fresh session — the planner will fan out and plan each child story.

    /github-issue-planner #150

**Why:** the planner posts the Epic-level plan first, then plans each child story and sequences them. Don't run the resolver on any story until its plan is posted.
```

**Revise mode (single issue or Epic).** What's next depends on whether a plan already exists for this issue and whether the revise materially changed scope, acceptance criteria, or the contracts the plan was built against (Step R6 already flags this — re-use that judgment for the handoff):

- **No plan exists yet** (`plan: ✗`) → forward to the planner to author one. Same shape as the first rendering above.
- **Plan exists and the revise was material** → the plan is now `stale`; forward to the planner in revise mode to refresh it.
- **Plan exists and the revise was cosmetic** (typo fix, link tidy, untouched contracts) → the plan stays current. Either the issue already has a PR in flight (terminal — issue and plan and PR are aligned, nothing for a follow-up skill to do here) or no work has started yet and the user can run the resolver when ready.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: stale

**Next:** refresh the plan in a fresh session — this revision materially changed scope.

    /github-issue-planner revise #142

**Why:** the revise reshaped the acceptance criteria (added bulk-export and removed PDF). The implementation plan from <date> assumed the previous shape; re-running the planner in revise mode rebuilds the plan against the new body before any code work resumes.
```

For an Epic revise that re-ordered or merged child stories (dimension-5 / dimension-7 surfacing during R-special-case), the `Why:` line cites the specific bullet change so the planner's re-audit can ground in evidence.

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
