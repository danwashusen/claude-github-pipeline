# Epic baseline comments (rendering)

The two epic-issue comments the epic-as-target route posts to record the canonical-suite baseline (spec
`docs/specs/resolver.md` "Artifacts written", rows "Epic issue comment — Baseline established" and
"— Baseline override"; source `github-issue-resolver/SKILL.md:797-812`). Render byte-for-byte per the
fixed bodies below and post through the single write path — stage the body to `facts.scratch` and
`gh_persist.py comment <owner/repo> issue <epic> "<staged>"` (SKILL.md §3). There is no S1
`docs/specs/examples/` capture for these; the spec's Artifacts-written table is the source these match.

## Baseline established

Posted on bootstrap, legacy recovery, or post-rectification, when the full canonical suite runs green in
the epic worktree. Fixed 4-field body under a header line:

```
🤖 Baseline established
- Epic branch SHA: <sha>
- Main SHA: <sha>
- Result: green
- Date: <iso-date>
```

- `Epic branch SHA` — the epic worktree HEAD the suite ran at. At the bootstrap fork point this equals the
  `MAIN_SHA` captured off `origin/main`; post-rectification it is the new (rebased/merged) epic HEAD.
- `Main SHA` — `git merge-base origin/main HEAD` in the worktree (equals `origin/main`'s tip on the rebase
  path; equals the `main` SHA merged in on the merge path; equals `MAIN_SHA` at the bootstrap fork).
- `Date` — `YYYY-MM-DD`.

## Baseline override

Posted when the operator overrides a red baseline on a story PR under an open epic (the red-baseline gate's
"explicit override with reason" branch). Fixed 3-field body under a header line:

```
🤖 Baseline override
- Story PR: #M
- Reason: <reason>
- Date: <iso-date>
```

- `Story PR` — the story PR `#M` whose baseline the operator overrode.
- `Reason` — the operator's recorded reason, verbatim.
- `Date` — `YYYY-MM-DD`.

Any later story under the epic re-establishes the baseline once the override condition clears.
