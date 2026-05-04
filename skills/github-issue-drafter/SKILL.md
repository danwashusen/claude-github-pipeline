---
name: github-issue-drafter
description: Drafts well-structured GitHub issues from informal developer feedback and files them via the `gh` CLI. Use this skill whenever the user describes a bug they hit, an incomplete or half-built feature they noticed, or a new feature idea — and wants it captured as a GitHub issue. Trigger this even when the user does not explicitly say "make an issue" — phrases like "I should track this," "let's file this," "we need to remember to fix X," "log this for later," or simply describing a problem in a repo context all qualify. Works best when the user is inside a git repository directory. Uses repo issue templates and labels if they exist, otherwise applies a consistent built-in format. Reads the project PRD (if one exists at `docs/prd.md` or similar) to ground feature framing and surface tensions between feedback and spec.
---

# GitHub Issue Drafter

Turn informal developer feedback into well-structured GitHub issues. The user is mid-development on a product and notices things — bugs, gaps, ideas. Your job is to capture those cleanly so future-them (or their team) has enough context to act.

## The core loop

1. **Classify** the feedback: bug, incomplete feature, or new feature.
2. **Check the repo** for existing conventions (templates, labels) — use them if present.
3. **Gather missing context** by asking the user, but only what's actually needed.
4. **Draft** the issue (title + body + labels + priority).
5. **Show the draft** to the user and wait for confirmation.
6. **File** via `gh issue create` only after the user approves.

Never skip step 5. Filed issues are annoying to clean up, and a 10-second confirmation prevents that.

## Step 1: Classify the feedback

The three types map to very different structures, so getting this right matters. Use these cues:

- **Bug** — Something is broken or behaving wrong. Cues: "X is broken," "this throws an error," "Y doesn't work when Z," past-tense problem reports, error messages, unexpected behavior.
- **Incomplete feature** — Something half-built that the user noticed while working on it. Cues: "I never finished," "this only works for X but not Y," "the empty state isn't handled," "TODO," "we stubbed this out."
- **New feature / enhancement** — A capability that doesn't exist yet. Cues: "users should be able to," "it would be nice if," "we need a way to," "I want to add."
- **Epic** — A multi-capability initiative too big to ship as a single PR; it decomposes into several Story issues. Cues: user lists multiple distinct capabilities in one breath ("we should do X, then Y, then Z"), scope crosses layers (UI + data + service), explicit phrasing like "this is going to be a big one," "multi-phase," "initiative," or the word "epic" itself. Heuristic: if the acceptance criteria the user has in their head won't fit in one shippable PR, it's likely an Epic.

**Feature vs. Epic — ask, don't promote.** Scope is the user's call. When detection signals fire, confirm with a single question ("This sounds Epic-sized — file as one feature, or as an Epic with child stories?") rather than silently upgrading. Filing a feature when the user wanted an Epic (or vice versa) is annoying to undo.

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

**Authoritative but mutable.** The PRD wins on framing and terminology by default, but if the user's feedback genuinely conflicts with it, surface that to the user explicitly: *"The PRD currently says X, but your feedback suggests Y. Should I file the issue to update the PRD, the feature, or flag the conflict for discussion?"* The user decides which way to go — don't silently override either the PRD or their feedback.

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

### Two-stage filing flow

**Stage 1 — File the Epic.** Draft using the Epic template (below). The `## Stories` section lists placeholder bullets — short titles only, no `#NN` yet:

```markdown
## Stories
- [ ] <Story 1 title>
- [ ] <Story 2 title>
```

File it, capture the Epic `#NN`.

**Stage 2 — Offer child-story filing.** After the Epic is filed, ask once:

> "Want me to file each story as a child issue too, or leave them as bullets for now?"

- **No** → done. The user can promote bullets to real issues later by hand.
- **Yes** → for each story: draft using the Story template with `**Epic:** #<epic-#> — <Epic title>` already filled in, confirm with the user (step 5, one story at a time — don't batch), file with the `story` label, collect the resulting `#NN`.

**Stage 3 — Stitch the Epic body.** Once all stories are filed, patch the Epic to replace placeholder bullets with real links:

```markdown
## Stories
- [ ] #42 — Story 1 title
- [ ] #43 — Story 2 title
```

```bash
cat > /tmp/epic-body.md <<'EOF'
<patched body>
EOF
gh issue edit <epic-#> --body-file /tmp/epic-body.md
rm /tmp/epic-body.md
```

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

## Step 5: Show the draft and confirm

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

Wait for explicit confirmation. "Yes," "file it," "looks good, go" — fine. Silence or a follow-up question — keep iterating.

## Step 6: File the issue

Use `gh issue create` with `--title`, `--body-file` (write body to a temp file to avoid shell escaping nightmares with multiline content and backticks), and `--label` flags:

```bash
# Write body to temp file
cat > /tmp/issue-body.md <<'EOF'
<body content>
EOF

# Create the issue
gh issue create \
  --title "<title>" \
  --body-file /tmp/issue-body.md \
  --label "bug" \
  --label "priority:medium"
```

Capture the URL `gh` returns and share it with the user. Clean up the temp file after.

If `gh` errors out (auth, label doesn't exist, etc.), report the exact error and what to do — don't silently retry with different flags.

### Filing an Epic with child stories

When the user opts into child-story filing after the Epic is created:

1. For each story in turn, write its body to `/tmp/story-body-N.md` (with the Epic backlink already filled in) and file it:
   ```bash
   cat > /tmp/story-body-N.md <<'EOF'
   **Epic:** #<epic-#> — <Epic title>
   ...
   EOF
   gh issue create \
     --title "<story title>" \
     --body-file /tmp/story-body-N.md \
     --label "story"
   ```
2. Collect each `#NN` as it's returned.
3. After all stories are filed, write the patched Epic body to `/tmp/epic-body.md` with placeholder bullets replaced by `- [ ] #NN — <Story title>` entries, then edit the Epic:
   ```bash
   gh issue edit <epic-#> --body-file /tmp/epic-body.md
   ```
4. Clean up all temp files.

## Handling edge cases

**User describes multiple things at once.** ("The export is broken AND we should add a dark mode toggle.") File these as separate issues. Confirm with the user that you're splitting them.

**User isn't in a repo directory.** `gh repo view` will fail. Ask which repo to file against and use `--repo owner/name` on the create command.

**User wants to file against a different repo than the cwd.** Honor that — pass `--repo` explicitly.

**Repo has issue templates but they don't fit.** Use the closest one and adapt. If genuinely none fits (e.g., they only have a "bug" template and the user wants to file a feature), use the built-in feature template.

**The feedback is too thin to file a useful issue.** Push back gently: "This is a bit thin — do you have a [reproduction step / persona / what 'done' looks like]? Otherwise we can file a stub and flesh it out later." Filing stubs is fine if the user prefers; just be honest about what's missing in the body.

## Why this matters

Issues are a primary artifact of product development. A vague issue costs the team 10x more in re-triage time than the 30 seconds saved when filing it. The skill's goal isn't speed — it's making sure each filed issue has enough context that anyone on the team (including future-you) can pick it up cold.
