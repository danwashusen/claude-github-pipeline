# Handoff renderings — github-issue-planner

Every clean run of the planner ends with a single `## Handoff` block. The schema, omission rules, and closed-set state-marker vocabulary live in [`../../_shared/handoff-format.md`](../../_shared/handoff-format.md); this file holds the planner's worked rendering shapes. Match the run's outcome to a shape and fill the snapshot from the data Step 12 lists.

### Renderings

**Single-issue plan posted.** Forward to the resolver.

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓ (https://github.com/owner/repo/issues/142#issuecomment-XXXXX)
**Grounding:** read at origin/main@a1b2c3d · docs/architecture.md §3 (service layer), §7 (export pipeline); docs/constitution.md §6 (logging) · external: RFC 4180 CSV spec (fetched 2026-06-20) · full detail in the plan's ## Doc grounding

**Next:** implement the plan in a fresh session.

    /github-pipeline:github-issue-resolver #142

**Why:** the plan locks architecture, file-level changes, layer assignments, and test strategy. The resolver executes against it and opens the PR; if implementation reveals a locked decision is wrong, it will re-route back here in revise mode.
```

**Epic plan posted (contracts + sequencing pinned); stories planned just-in-time.** Forward to the **planner** on the first story in dependency order — each story's full plan is authored just-in-time against current epic HEAD, not up front. The Epic's `## Story breakdown` names the order (top-to-bottom); pick the head of it. The `Grounding:` ref is `origin/main` here — the bootstrap case, before the `epic/<N>-<slug>` branch exists (it's created when the first story is implemented); a later epic *re-plan*, once the branch exists, grounds at `epic/<N>-<slug>@<sha>` instead.

```
## Handoff

**Epic:** #150 — Chat & session UX polish · open · epic · plan: ✓
**Stories:** #151, #152, #153, #154, #155 (5 filed, dependency-ordered, contracts pinned · plans authored just-in-time)
**Grounding:** read at origin/main@b2c3d4e · docs/architecture.md §2 (layer rules), §5 (session model); docs/ui-design.md §4 (chat-size model); docs/constitution.md §2 (layering) · full detail in the plan's ## Doc grounding

**Next:** plan the first story in dependency order, just-in-time, in a fresh session.

    /github-pipeline:github-issue-planner #151

**Why:** the epic plan pins the cross-story contracts and sequencing; each story is planned just-in-time against the epic branch HEAD as it becomes the next to build, so it never grounds on code a predecessor has since moved. #151 is the head of `## Story breakdown` — planning it produces its story plan, then the resolver implements it against `epic/150-chat-ux`.
```

**Just-in-time story plan posted.** A story under an open epic was planned against current epic HEAD. Forward to the resolver on that story.

```
## Handoff

**Story:** #151 — Add export service · open · story · plan: ✓ (https://github.com/owner/repo/issues/151#issuecomment-XXXXX)
**Epic:** #150 — Chat & session UX polish · open (0 of 5 stories closed)
**Grounding:** read at epic/150-chat-ux@c3d4e5f · docs/architecture.md §3 (service layer); docs/constitution.md §8 (schema/migrations) · full detail in the plan's ## Doc grounding

**Next:** implement the story in a fresh session.

    /github-pipeline:github-issue-resolver #151

**Why:** #151's plan was authored just-in-time against `epic/150-chat-ux` HEAD and checked against the epic's `## Story contracts` (Dimension 8). The resolver opens a PR targeting the epic branch; when it merges, the evaluator hands off to plan the next story just-in-time.
```

If the Epic ran but the child stories weren't filed yet (Step 11's "stop after the epic-level plan" branch), the next step is the drafter — that's a forward route to file the stories, then the user re-runs the planner on the Epic. As with the epic-plan rendering, `Grounding:` reads at `origin/main` — bootstrap, before the epic branch exists:

```
## Handoff

**Epic:** #150 — Chat & session UX polish · open · epic · plan: ✓ (https://github.com/owner/repo/issues/150#issuecomment-XXXXX)
**Stories:** plain bullets (not yet filed as issues)
**Grounding:** read at origin/main@d4e5f6a · docs/architecture.md §2 (layer rules), §5 (session model); docs/ui-design.md §4 (chat-size model) · full detail in the plan's ## Doc grounding

**Next:** file the child stories in a fresh session, then re-run the planner on the Epic.

    /github-pipeline:github-issue-drafter

**Why:** the planner doesn't file issues — that's the drafter's job. Once the stories are filed (each with the `**Epic:** #150` backlink), re-run `/github-pipeline:github-issue-planner #150` to refresh the epic plan, then plan each story just-in-time (`/github-pipeline:github-issue-planner #<story>`) as you build it.
```

**Trivial change — planner declined to author a plan.** Forward straight to the resolver.

```
## Handoff

**Issue:** #142 — Fix typo in onboarding copy · open · bug · plan: ✗

**Next:** implement the fix in a fresh session.

    /github-pipeline:github-issue-resolver #142

**Why:** this issue is a one-line copy fix — no implementation plan is warranted (the planner's Step 3 scale-to-work judgment). The resolver opens the PR directly.
```

**Knowledge gap — re-route to the researcher.** When Step 5's grounding hit external truth you couldn't reliably recall and the gap was too broad for an inline fact-check, stop and route to the researcher instead of posting a plan built on a guess. The `Why:` names the specific ungroundable fact so the researcher targets exactly that gap.

```
## Handoff

**Issue:** #142 — Migrate to <dependency> v<X> · open · feature · research: ✗ · plan: ✗

**Next:** gather and verify the current behaviour the plan depends on, in a fresh session.

    /github-pipeline:github-issue-researcher #142 — current supported API for <dependency> v<X>; was the pre-v<X> approach deprecated?

**Why:** the plan turns on <dependency> v<X> behaviour that postdates my training cutoff — planning on recall would lock a guess. The researcher posts a cited dossier; re-run `/github-pipeline:github-issue-planner #142` afterward and Step 4 ingests it.
```

**Revise mode — plan refreshed.** Same forward shape; the plan URL in the `Issue:` line is the *new* comment URL captured at Step 10 (the stale one was deleted via `delete_marker_id`).

```
## Handoff

**Issue:** #142 — Add CSV export · open · feature · plan: ✓ (https://github.com/owner/repo/issues/142#issuecomment-YYYYY)
**Grounding:** read at issue-142-add-csv-export@e5f6a7b · docs/architecture.md §3 (service layer), §7 (export pipeline); docs/constitution.md §6 (logging) · full detail in the plan's ## Doc grounding

**Next:** resume implementation in a fresh session.

    /github-pipeline:github-issue-resolver continue #287

**Why:** the plan was refreshed against today's codebase (the `<X>` symbol the previous plan named was renamed to `<Y>` at `<path:line>`). PR #287 is still open on the same branch; the resolver continues from there with the updated locked decisions.
```

If no PR exists yet (the resolver hasn't started), drop the `continue #287` and use `/github-pipeline:github-issue-resolver #142` instead.
