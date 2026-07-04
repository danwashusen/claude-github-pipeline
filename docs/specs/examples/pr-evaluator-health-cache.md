# Example — `<!-- pr-evaluator-health-cache:v1 -->` health-cache comment (schema definition)

> Artifact: the `<!-- pr-evaluator-health-cache:v1 -->` health-cache comment (prd.md §7, row 7).
> Source: `skills/github-pr-evaluator/SKILL.md:300-328` (§5.6 "Write the cache comment").
> This is a **schema/template definition**, not a worked instance — the canonical example is this
> template block, verbatim, exactly as the evaluator composes and posts it, and re-reads it on a
> subsequent run's cache-hit path (§5.2). Note the block contains a **nested** fenced code span
> (the `<FAIL_TAIL>` example) — the outer fence below therefore uses four backticks so the inner
> three-backtick fence renders literally, exactly matching what the source file does at
> `SKILL.md:323,325`.

````
<!-- pr-evaluator-health-cache:v1 -->
**Health checks** at `<short-sha>` — <all green ✅ | N failed ❌ | local-green over red CI ⚠️> — <ISO-8601 UTC timestamp>

SHA: <full-sha>
TIER: <targeted | full>
Source: COMMANDS.md / CLAUDE.md

**Selection reasoning** (from §5.5.2 sub-agent):
> <SELECTION_REASONING verbatim — the sub-agent's RATIONALE: section. Multi-line
> rationales render as one block-quote line per logical line. Omit the entire
> block when test selection didn't run, e.g. when static checks failed before
> §5.5.2 fired.>

| Command | Status | Duration |
|---|---|---|
| `<cmd-1>` | ✅ pass | 1.2s |
| `<cmd-2>` | ❌ fail (exit 1) | 3.8s |
| `<cmd-3>` | ⏭ skipped | — |
| `<COMMAND from §5.5.2>` | ✅ pass | 28s |

<details>
<summary>Failed: `<cmd-2>` — last 50 lines</summary>

```
<FAIL_TAIL>
```
</details>

_Cached by `github-pr-evaluator`. Do not edit; will be regenerated when HEAD changes._
````

Keyed per head SHA — the comment is deleted and reposted (never edited in place) whenever
`HEAD_SHA` changes (`SKILL.md:131-134,331-335`). The first-line state token is one of exactly
three: "all green ✅", "N failed ❌", "local-green over red CI ⚠️" (the CI/local discrepancy gate's
operator-override outcome). `TIER:` is `targeted` or `full`; a comment with no `TIER:` line
predates targeting and is read as `full` (`SKILL.md:131`).
