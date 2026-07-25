# Health-cache comment rendering — `<!-- pr-evaluator-health-cache:v1 -->`

The evaluate spine's S3.5 stages and posts this comment. It is a **prd.md §7-frozen artifact** — the
schema and semantics must not change, and this rendering is byte-compatible with the S1 baseline
(`docs/specs/examples/pr-evaluator-health-cache.md`). Compose exactly this template, stage it to
`<facts.scratch>/health-cache.md`, and post it via `gh_persist.py comment … pr <PR>` (with
`--delete-marker-id` when a stale comment exists). The marker `<!-- pr-evaluator-health-cache:v1 -->`
is the first line.

The block below contains a **nested** fenced code span (the `<FAIL_TAIL>` example), so the outer fence
uses four backticks so the inner three-backtick fence renders literally — matching the frozen example.

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

Rules (from the frozen schema):
- Keyed **per head SHA** — the comment is deleted and reposted (never edited in place) whenever the PR
  head SHA changes. On a stale cache, pass the prior comment's id as `--delete-marker-id`.
- The **first-line state token** is one of exactly three: `all green ✅`, `N failed ❌`, `local-green
  over red CI ⚠️` (the CI/local discrepancy gate's operator-override outcome).
- `TIER:` is `targeted` or `full`. A comment with no `TIER:` line predates targeting and is read as
  `full`.
- The `_Cached by `github-pr-evaluator`._` footer is preserved **verbatim** — it is the marker text a
  reader recognizes on the PR; the v2 skill is named `evaluator` but the artifact string is a frozen
  contract token and does not change.
- Omit the `**Selection reasoning**` block entirely when test selection didn't run (e.g. static checks
  failed first). Omit the `<details>` fail block when nothing failed.
