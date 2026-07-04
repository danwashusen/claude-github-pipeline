# setup — v1 functional spec (baseline)

> Source: `skills/github-pipeline-setup/SKILL.md` (338 lines) + references:
> `references/block-authoring.md` (490 lines); `_shared/worktree-lifecycle.md` (158 lines),
> `_shared/asking-the-user.md` (30 lines).
> Captures v1 behavior as the parity baseline for [implementation.md](../implementation.md) S17.
> v1 skill name: `github-pipeline-setup`; v2 name: `setup`.

## Overview

`github-pipeline-setup` is a standalone, non-pipeline tool that makes a consuming repository ready
for the other github-pipeline skills. The resolver, evaluator, and (for open-question markers) the
drafter/planner carry no per-project configuration of their own — they read it at use-time from
marker-delimited command blocks the consuming repo declares in `COMMANDS.md` (preferred) or
`CLAUDE.md`. This skill is the single writer of those blocks: it inventories what a repo already
declares, detects and grounds candidate commands from repo evidence (CI workflows, task-runner
manifests, `scripts/*.sh`), interviews the operator for what can't be inferred (naming conventions,
merge-policy preference, worktree hook need), confirms every draft as an explicit diff, writes via
the bundled `config-block.sh` script, and offers a light post-write validation. Session shape: single
interactive session, `opus`/`medium` (SKILL.md:3-4). Report-then-apply and explicit-invocation in
practice — SKILL.md's own prose frames every write as gated behind an operator confirm (SKILL.md:17-22,
315-316) — but v1's frontmatter does not carry `disable-model-invocation: true` (see Known bugs for
why this spec's own brief, not v1, is the source of that expectation). Inputs: the target repo's
working tree and its existing
`COMMANDS.md`/`CLAUDE.md`. Outputs: written/reconciled config-block(s) in the consuming repo's
tracked Markdown files — never GitHub state. It ends with a plain **Summary** (SKILL.md:295-310), not
a pipeline `## Handoff` — setup is explicitly not a pipeline stage (SKILL.md:28-30).

## Artifacts written

All eleven blocks below are **consuming-repo local-file config**, not GitHub markers — this skill
never calls `gh`. (SKILL.md:74 itself says "Seven blocks across two consumer skills, the
worktree-lifecycle pair, one general operating-guidance block … and the `github-pipeline-config`
file header" — the "seven" counts only the resolver/evaluator command-and-policy blocks, i.e. the
first category before "the worktree-lifecycle pair, one … block, and the … header" add the other
four; its own table two lines later, SKILL.md:82-94, lists all eleven rows reproduced below. Both
numbers are the source's own, describing the same set at different granularity — not a
contradiction to silently resolve one way.) Every block is written exclusively through
`${CLAUDE_PLUGIN_ROOT}/scripts/config-block.sh upsert <file> <marker> <body-path>`
(SKILL.md:47-70); nothing is ever hand-`sed`/`Edit`/`Write`-rolled onto these blocks directly (the
one exception is removing a *legacy freeform preamble*, which is not a marker block — SKILL.md:255-258).

| Marker | Lives in | Shape | Trigger (when in flow) |
|---|---|---|---|
| `<!-- issue-resolver-fast-checks -->` | `COMMANDS.md` (preferred) or `CLAUDE.md` | command-list | §5 write, after §4 confirm |
| `<!-- issue-resolver-test-target -->` | same | prose config | §5 write |
| `<!-- issue-resolver-canonical-suite -->` | same | 3 labelled commands | §5 write (skipped on no-epic-flow projects) |
| `<!-- pr-evaluator-static-checks -->` | same | command-list | §5 write |
| `<!-- pr-evaluator-test-target -->` | same | prose config + `full-suite-command` | §5 write |
| `<!-- pr-evaluator-escalation-labels -->` | same | label list (may be empty) | §5 write |
| `<!-- pr-evaluator-merge-policy -->` | same | key/value list (`standard`/`story`: `ask`\|`auto`) | §5 write, interview-only (not detected) |
| `<!-- worktree-setup -->` | same | command-list (optional) | §5 write, research-and-propose, opt-in on stateful-resource signal |
| `<!-- worktree-teardown -->` | same | command-list (optional) | §5 write, always proposed as a pair with `worktree-setup` |
| `<!-- claude-code-stack-profile -->` | **CLAUDE.md only** (or a file it `@`-includes) | free prose (optional) | §5 write, research-and-propose, default-on for any recognized stack |
| `<!-- github-pipeline-config -->` | **COMMANDS.md only**, file-header, via `--prepend` | fixed canonical one-paragraph notice | §5 write, only when the pipeline-config target file is `COMMANDS.md` |

**Canonical body / shape for each** (verbatim from `references/block-authoring.md`):

- **`issue-resolver-fast-checks`** (block-authoring.md:57-61):
  ```markdown
  <!-- issue-resolver-fast-checks -->
  - `<command>` — <description>
  <!-- /issue-resolver-fast-checks -->
  ```
  Fail-fast static-only commands (codegen, dep resolution, lints, layer-import boundary checks); no
  test invocations. Order matters — fail-fast, cheapest first (block-authoring.md:37-38,51-56).

- **`issue-resolver-test-target`** (block-authoring.md:69-78):
  ```markdown
  <!-- issue-resolver-test-target -->
  - wrapper: `<test-runner command>`
  - targets:
    - `<TargetName>` (unit | UI)
      - naming: <how source files map to suite identifiers>
      - helpers-fallback: <command, or "none">
      - broad-change-fallback: <command, or "none">
  <!-- /issue-resolver-test-target -->
  ```

- **`issue-resolver-canonical-suite`** (block-authoring.md:93-99):
  ```markdown
  <!-- issue-resolver-canonical-suite -->
  - full-suite: `<one-shot canonical command>`
  - build-once: `<compile-the-test-bundle-once command>`
  - retry-without-rebuild: `<re-run-without-recompile command>`
  <!-- /issue-resolver-canonical-suite -->
  ```
  All three collapse to the same command on stacks that can't separate compile from run
  (block-authoring.md:101-104).

- **`pr-evaluator-static-checks`** (block-authoring.md:112-116): same shape/rules as
  `issue-resolver-fast-checks`; commands are repo-root-relative (evaluator `cd`s into the branch
  worktree first).

- **`pr-evaluator-test-target`** (block-authoring.md:123-133): same as
  `issue-resolver-test-target` plus one extra line, `full-suite-command:`, run on escalation
  (epic-integration PR or an escalation-label match).

- **`pr-evaluator-escalation-labels`** (block-authoring.md:145-150):
  ```markdown
  <!-- pr-evaluator-escalation-labels -->
  - `full-suite-required` — bypass targeted selection
  - `pre-release` — run everything before a release cut
  <!-- /pr-evaluator-escalation-labels -->
  ```
  Empty/absent means "no label-based escalation" — a valid, normal choice (block-authoring.md:141-143).

- **`pr-evaluator-merge-policy`** (block-authoring.md:158-163):
  ```markdown
  <!-- pr-evaluator-merge-policy -->
  - standard: ask
  - story: ask
  <!-- /pr-evaluator-merge-policy -->
  ```
  Keys are exactly `standard` and `story`; values `ask`|`auto`; default (absent block, or a type
  omitted from a present block) is `ask`; `epic-integration` is not a valid key and is ignored if
  present (block-authoring.md:165-172). Not detected from the repo — a pure preference; setup
  proposes `ask`/`ask` and interviews for opt-in `auto` (SKILL.md:179-185, block-authoring.md:173-175).

- **`worktree-setup` / `worktree-teardown`** (block-authoring.md:192-200) — see
  `_shared/worktree-lifecycle.md:79-88` for the canonical block format (same shape — worktree
  blocks are per-repo user-authored command lists with no frozen fixed body, so the two sources'
  illustrative command-line counts differ). Command-list shape; parser constraint: each command
  must be a single backtick-quoted span on one line with no embedded backtick, or
  `worktree-hooks.sh` silently drops it (block-authoring.md:208-211).

- **`claude-code-stack-profile`** (block-authoring.md:233-239):
  ```markdown
  <!-- claude-code-stack-profile -->
  ## Running this stack with Claude Code

  <concise operating guidance — see scope and constraints below>
  <!-- /claude-code-stack-profile -->
  ```
  Free prose, no parser constraint (nothing extracts spans from it — model-read via CLAUDE.md
  auto-load) (block-authoring.md:241-243). Two worked examples given verbatim for Rails
  (block-authoring.md:271-283) and Node/TS (block-authoring.md:285-296).

- **`github-pipeline-config`** header (block-authoring.md:312-316), verbatim:
  ```markdown
  <!-- github-pipeline-config -->
  Pipeline configuration for the `github-pipeline` skills (resolver / evaluator / planner), read at use-time. You can edit these blocks by hand — just keep each block's `<!-- … -->` marker pair intact so the skills can find it. Re-run `github-pipeline-setup` to reconcile them (idempotent).
  <!-- /github-pipeline-config -->
  ```
  Written with `--prepend` so it heads `COMMANDS.md` (block-authoring.md:308-310). Never substitute
  an "edit only via setup / not by hand" message — hand-edits are explicitly allowed
  (SKILL.md:228-230, block-authoring.md:320-321).

**Ownership split** (SKILL.md:96-105): the nine machine-parsed blocks plus `github-pipeline-config`
are **plugin-owned** — setup is their single write path and reconciles each to canonical form on
every run (a re-run restores exact wording). `claude-code-stack-profile` is the lone **user-owned**
exception: setup seeds it when absent, and on re-run **re-ingests the existing interior as the base**
and proposes only currency refinements layered on top — never wholesale-replaces user prose
(SKILL.md:211-216, block-authoring.md:227-231).

## Artifacts read

- **Any existing block from the table above**, via `config-block.sh read <file> <marker>` (interior
  text) and `config-block.sh list <file>` (inventory: `<status> <name>` per line, status one of
  `ok`/`open`/`dup`) (SKILL.md:47-61). Used in §2 (inventory — reconcile vs. re-create) and §4
  (diff-against-current for the confirm step).
- **A legacy `<!-- pr-evaluator-health-checks -->` block** — the pre-split single block holding both
  static commands and the test invocation as one flat command list (SKILL.md:133-134, 260-265;
  block-authoring.md:385-399). Read via `config-block.sh read`, then split.
- **A legacy freeform preamble** — top-of-file prose *above* the first marker block (e.g. an old
  "edit only via setup" notice or a bare `# COMMANDS.md` title) that predates the managed
  `github-pipeline-config` header (SKILL.md:136-139). Detected by inspection, not by
  `config-block.sh` (it isn't a marker block).
- **Repo evidence for detection** (SKILL.md:154-160, block-authoring.md:323-359): `package.json`
  scripts, `Makefile` targets, `scripts/*.sh`, CI workflows (`.github/workflows/*.yml`),
  project-type manifests (`Package.swift`, `go.mod`, `pyproject.toml`, `Cargo.toml`,
  `pom.xml`/`build.gradle`, `Gemfile`), and the working tree itself (to ground/verify a candidate
  command — e.g. real test files backing a proposed target, via `Glob`/`find`/`git ls-tree`).
- **`gh auth status`, `command -v jq/git/gh`, `git rev-parse --is-inside-work-tree`** — preflight
  environment reads (SKILL.md:118-122), report-only, never acted on.

## Operator gates

Every gate routes through `AskUserQuestion` per `_shared/asking-the-user.md` (SKILL.md:32-38):
one decision per card, `header` ≤ 12 chars, imperative `label`s with consequence-bearing
`description`s, options generated from what was actually found (asking-the-user.md:9-15).

- **Target-file choice** (SKILL.md:143-145, 313-314): when neither `COMMANDS.md` nor `CLAUDE.md`
  exists, or blocks are split across both, ask which file is canonical before writing anything.
  Default proposal when neither exists: create `COMMANDS.md`.
- **Same marker declared in both files** (SKILL.md:140-141): flagged as an ambiguity (the pipeline
  skills scan both); ask which file is canonical, plan to `remove` the duplicate from the other.
- **Per-block confirm before every write** (SKILL.md:232-246, 315-316): show each drafted block as a
  diff against current content; gate with a per-block confirm, or one "write all N as shown / let me
  edit / cancel" card when drafts are clean. Even a clean greenfield write is confirmed — nothing is
  ever written silently.
- **Ambiguous / empty detection** (SKILL.md:186-188, 320-322): when several plausible test wrappers
  exist, or no static checks are found, present what was found and let the user pick or explicitly
  accept an empty block — never wire in a guess.
- **`pr-evaluator-merge-policy` preference interview** (SKILL.md:179-185): ask which PR types
  (`standard`, `story`) should gate on a human vs. merge hands-free; propose `ask`/`ask` as the
  default framing.
- **`issue-resolver-test-target` / `pr-evaluator-test-target` naming interview** (SKILL.md:171-173):
  detection gets the wrapper and target names; interview the user for the per-target naming
  convention and the two fallbacks rather than inventing them.
- **`worktree-setup`/`worktree-teardown` propose-as-pair confirm** (SKILL.md:190-203): only proposed
  when a shared stateful test dependency is detected; researched-then-proposed commands are
  confirmed by the operator, with the idempotent-by-construction contract stated explicitly.
- **`claude-code-stack-profile` diff framing** (SKILL.md:238-240): a present block's diff must be
  framed as "your content + proposed currency updates" — the default proposal is to keep the
  existing block; the user's own prose is never shown as a wholesale deletion.
- **Legacy freeform-preamble replacement confirm** (SKILL.md:242-244): when replacing top-of-file
  prose with the `github-pipeline-config` header, show the removed lines alongside the new block so
  the user approves the swap, not just an addition.
- **Legacy `pr-evaluator-health-checks` migration opt-in** (SKILL.md:260-265, 317-318): confirm the
  static/test-target split before `remove`-ing the original — restructures the user's declaration and
  infers test-target prose, a judgment call worth a look.
- **Offer to dry-run fast/static checks** (SKILL.md:267-277, 319): after writing, offer (never force)
  to run the `*-fast-checks`/`*-static-checks` lists once, in declared order, reporting pass/fail per
  command. Never auto-runs a `test-target` full suite (can be long-running, may have side effects).
- **Preflight gaps are reported, never auto-fixed** (SKILL.md:113-116, 337-338): missing `jq`/`git`/`gh`
  or an unauthenticated `gh` are surfaced with a one-line fix each; setup never logs in, installs, or
  modifies the user's machine.

## Judgment steps (model reasoning — stays in the prompt)

All in the **main loop** — this skill dispatches no isolated sub-agent (see "Sub-agents dispatched").

- **Inventory classification** (§2, SKILL.md:127-152): classify every known marker as present /
  legacy / malformed / missing; detect a legacy freeform preamble; decide the target file.
- **Detection and drafting** (§3, SKILL.md:154-231): scan repo evidence, apply the per-block
  detection heuristics (block-authoring.md:323-359, stack-specific tables for Node/TS, Go, Python,
  Swift/Apple, Ruby/Rails, Make), and **ground** every candidate against the working tree before
  proposing it (block-authoring.md:361-384) — verify a script/target/tool exists, or that real test
  files back a proposed suite; exclude anything that can't be grounded and say so.
- **`worktree-*` research-and-propose** (SKILL.md:190-203, block-authoring.md:202-211): judge whether
  the repo shows a shared stateful test dependency (DB/dev server, simulator, bound port,
  branch-keyed cache) that warrants the pair; if so, research best-practice per-worktree provisioning
  for the detected stack, run a lightweight web check for currency, escalate to fuller web research
  for an unfamiliar stack or an uncertain draft.
- **`claude-code-stack-profile` research-and-propose** (SKILL.md:205-222, block-authoring.md:213-266):
  default-on for any recognized stack (not a rare-signal opt-in like `worktree-*`); default-on
  currency check via a lightweight web check every run, escalating to fuller research for an
  unfamiliar stack; on a present block, propose only refinements to genuinely stale idioms layered on
  the user's existing content. Scope discipline: operating/efficiency layer only (backgrounding,
  log-and-grep, terse formatters, parallelism/per-worker resources) — never coding conventions, never
  a plain command list, always surface-don't-suppress (redirect-then-read-back, never hide output).
- **Diff presentation** (§4, SKILL.md:232-246): render each drafted block as a diff against current
  content in a form the user can actually evaluate byte-for-byte.
- **Post-write validation review** (§6, SKILL.md:267-293): interpret dry-run pass/fail per command,
  and interpret `worktree-hooks.sh lint`'s `would_run` list / `MALFORMED_BLOCK` exit against what the
  operator approved, surfacing a mismatch (dropped/truncated command, duplicated/unterminated block)
  for the operator to fix.
- **Summary composition** (§7, SKILL.md:295-310): compact written/reconciled/already-correct/skipped
  report per block, using the plugin-owned vocabulary for the nine machine-parsed blocks plus the
  plugin-owned-but-not-machine-parsed `github-pipeline-config` header, and a distinct
  seeded/refreshed/already-current vocabulary for the user-owned `claude-code-stack-profile`;
  outstanding preflight ✗s; a copy-pasteable "next step" pointer (not a pipeline command, since there
  is no session state to carry forward).

## Deterministic steps (candidate script work — moves to a prep/executor script)

- **`config-block.sh read <file> <marker-name>`** — print a block's interior to stdout. Exit 3 if the
  named block is absent (SKILL.md:59-60; scripts/config-block.sh:103-117, exit-code table at
  scripts/config-block.sh:40-46).
- **`config-block.sh list <file>`** — print `<status> <name>` per discovered marker: `ok`
  (well-formed), `open` (unterminated), `dup` (declared twice) (SKILL.md:59-61;
  scripts/config-block.sh:119-138). A nonexistent `<file>` exits 0 with empty stdout — "no file" is
  treated as "no blocks," not an error (scripts/config-block.sh:122) — a case neither SKILL.md nor
  this spec's Artifacts-read section states explicitly; noted here since §2's inventory step calls
  `list` on `COMMANDS.md`/`CLAUDE.md` before confirming either exists.
- **`config-block.sh upsert <file> <marker-name> <body-path> [--dry-run] [--prepend]`** — replace an
  existing block's interior in place, or append a fresh one in canonical form; `--prepend` places a
  *newly created* block at the top of the file (no-op — position unchanged — once the block already
  exists, so re-running stays idempotent) (SKILL.md:55-58, 254-258; scripts/config-block.sh:169-220,
  25-27). Body is staged to a scratch file (`/tmp/gh-setup-<repo>/<marker>.md`) via `Write`, then
  passed by path — never re-inlined on a command line (SKILL.md:67-70). Returns a one-line JSON
  envelope: `{op, marker, file, changed, dry_run, body_bytes, body_sha256}` — `changed: false` means
  the file was byte-identical and literally untouched on disk (SKILL.md:56-58;
  scripts/config-block.sh:48-56, 140-167). An absent target file is treated as empty input, so
  `upsert` can create the file from scratch (scripts/config-block.sh:186-188).
- **`config-block.sh remove <file> <marker-name> [--dry-run]`** — delete a block plus one blank line
  immediately above it (SKILL.md:62); idempotent no-op (with `changed:false`) if the file or the
  block doesn't exist (scripts/config-block.sh:233-238, 244).
- **Malformed-input refusal, not guessing** — a marker name failing `^[A-Za-z0-9:_-]+$` exits 2
  (`INVALID_MARKER_NAME`); a duplicated marker exits 4; an unterminated one exits 5
  (SKILL.md:63-65; scripts/config-block.sh:75-81, 40-46). Surfaced to the user rather than worked
  around — a doubly-declared block means the repo is already in a state the pipeline skills would
  also trip on.
- **`worktree-hooks.sh lint <setup|teardown> <repo_root>`** — parse-only validation of the final
  written form: discovers and parses the phase's block and lists `would_run` **without** creating a
  worktree or running anything (SKILL.md:280-288). Emits `{op:"lint", phase, phase_present,
  command_count, would_run}` on success; exits 2 on two distinct failures, both undifferentiated by
  SKILL.md's own prose (which names only the first): a duplicated/unterminated block prints
  `MALFORMED_BLOCK` on stderr with no `would_run` (scripts/worktree-hooks.sh:35-59, 128, 253-271), and
  a `<repo_root>` argument that doesn't exist as a directory prints `REPO_ROOT_NOT_FOUND` on stderr
  instead (scripts/worktree-hooks.sh:260) — both are bare exit 2 with different stderr text, so a
  caller distinguishes them by message, not exit code. This is the
  only validation step for `worktree-*` blocks and is always run (executes nothing, so there's no
  reason to skip it) — contrast with the dry-run execution offered for `*-fast-checks`/`*-static-checks`.
- **Detection-heuristic parsing** (block-authoring.md:323-359) — scanning `package.json` `scripts`,
  `Makefile` targets, CI workflow YAML, `scripts/*.sh`, and project-manifest files to produce
  candidate commands per stack. Concrete input → output: e.g. a `package.json` with `scripts.test` →
  candidate `issue-resolver-test-target.wrapper = npm run test`; a `Gemfile` + `test/system/**/*_test.rb`
  → candidate `pr-evaluator-test-target` system target.
- **Grounding a candidate against the tree** (block-authoring.md:361-384) — for a static/fast check:
  confirm the invoked script/target/tool exists; for a test target/suite: confirm real test files
  back it (`Glob`/`find`/`git ls-tree`); for canonical/full-suite: confirm the chained sub-suites
  exist. Deterministic existence checks, currently done by the model via tool calls.
- **Legacy `pr-evaluator-health-checks` → static-checks + test-target split**
  (block-authoring.md:385-399): read the legacy block; static-looking commands (lints, codegen, dep
  resolution, boundary checks) route to `pr-evaluator-static-checks`; the test invocation becomes both
  `wrapper` and `full-suite-command` in a `pr-evaluator-test-target` draft (naming/fallbacks not
  recoverable from a flat list — interviewed, or carried over from a matching
  `issue-resolver-test-target` if one exists).
- **Preflight checks** (SKILL.md:118-122): `git rev-parse --is-inside-work-tree`, `command -v
  jq/git/gh`, `gh auth status` — pure environment probes with a fixed pass/fail → readiness-line
  mapping, no judgment involved.

## Invariants (with the WHY)

- **Idempotency lives in deterministic code, never in a model-landed edit** (SKILL.md:42-44). WHY:
  "run it again and nothing breaks" is the whole point of the skill; trusting the model to reproduce
  byte-identical output on every re-run (rather than a script that literally diffs-and-no-ops) would
  make the guarantee only as good as the model's care that session.
- **Never hand-roll `sed`/`Edit`/`Write` against a marker block** (SKILL.md:43-45, 325-327). WHY:
  re-opens the exact duplicate-block / drift-on-re-run failure modes `config-block.sh` exists to
  prevent, mirroring the reason the pipeline skills route all `gh` I/O through the bundled scripts
  rather than hand-rolled `gh` calls.
- **Stage the body to a scratch file, then pass the path — never re-inline on a command line**
  (SKILL.md:67-70). WHY: same discipline as `gh-persist.sh`'s empty-body gate — keeps the exact bytes
  intact and keeps `upsert` deterministic; nothing re-serializes the body across a prompt boundary.
- **Malformed input (`dup`/`open`) is refused, not guessed around** (SKILL.md:63-65). WHY: a block
  declared twice, or left open, means the repo is *already* in a state that would also confuse the
  resolver/evaluator parsers at runtime — silently picking one interpretation would hide that the
  repo needs a human fix.
- **Setup is the only place the plugin writes the pipeline-config blocks** (SKILL.md:17-22). WHY: the
  resolver and evaluator both refuse to write these blocks silently ("always ask the user before
  modifying project files") — that confirmation belongs here, in one place the user can see exactly
  what's going in, not scattered across whichever pipeline skill happens to notice a gap.
- **A hand-edit that keeps the `<!-- … -->` markers intact is always fine** (SKILL.md:20-24, 228-230,
  320-321). WHY: plugin-ownership governs the plugin's own *automated* writes, not the human; the
  `github-pipeline-config` header must say so explicitly (never "edit only via setup"), because a
  false "hands off" notice would fight a legitimate manual fix.
- **`claude-code-stack-profile` is user-owned: re-ingest, never overwrite** (SKILL.md:24-26, 211-216;
  block-authoring.md:227-231). WHY: unlike a machine-parsed block, its value is the model consuming
  current, project-specific prose every session — clobbering the user's accumulated tuning back to a
  generic draft on every re-run would destroy exactly the thing that makes it worth having.
- **Never fabricate a command** (SKILL.md:186-188, 328-332; block-authoring.md:380-384). WHY: an
  invented `npm test` that cold-rebuilds, or a static check that doesn't exist, is *worse* than an
  absent block — the pipeline skill would at least ask about a missing block at runtime, but a
  silently-wired bad command fails opaquely later, possibly mid-resolver-run.
- **A source naming a command is a candidate, not proof it runs — ground before writing**
  (block-authoring.md:328-335, 361-376). WHY: scaffold generators ship CI jobs and test-target stubs
  for suites that were never actually written (a fresh `rails new`'s `system-test` CI job, an empty
  `<App>UITests` bundle) — a *green* CI job names the suite, it doesn't prove the suite has tests.
- **Be conservative when grounding: drop only on positive evidence of absence** (block-authoring.md:369-371).
  WHY: over-pruning a real-but-hard-to-detect command is also a failure mode; when uncertain, keep the
  candidate and let the §6 dry-run or a user confirm catch it, rather than silently omitting something
  real.
- **Static-check lists exclude tests** (block-authoring.md:378-379). WHY: the two block families have
  different failure semantics (fail-fast hygiene vs. targeted/full test selection) — folding a
  "test everything" command into a static list breaks the resolver/evaluator's fast-first ordering
  assumption.
- **Keep each config marker in exactly one file** (SKILL.md:140-141, 335-336). WHY: the pipeline
  skills scan both `COMMANDS.md` and `CLAUDE.md` for a marker — the same name present in both makes
  "which one wins" ambiguous for every downstream reader, not just setup.
- **`worktree-setup` and `worktree-teardown` are always proposed as a pair** (SKILL.md:198-199;
  block-authoring.md:203-205). WHY: setup that allocates a per-worktree resource (simulator, port,
  scratch DB) must ship with the teardown that releases it, or the resource leaks on every worktree
  the resolver creates.
- **Worktree-hook commands must be idempotent by construction** (SKILL.md:199-202;
  `_shared/worktree-lifecycle.md`:41-55). WHY: setup re-runs on every worktree entry (not just
  creation) and teardown runs best-effort on possibly-half-provisioned state — guard-then-create is
  the only shape that survives both.
- **Worktree-hook commands must be one backtick-quoted span per line, no embedded backticks**
  (block-authoring.md:208-211). WHY: `worktree-hooks.sh` extracts the *first* backtick span per
  list item; a multi-line or backtick-containing command is silently dropped from what actually runs
  — a silent drop is far worse than a rejected block, because the operator believes the hook is wired
  when it isn't.
- **`pr-evaluator-merge-policy` defaults to `ask` for everything, `auto` strictly opt-in**
  (block-authoring.md:167-169, 173-175). WHY: this is the evaluator's merge-gate default too — a
  repo with zero configuration still gets human-in-the-loop merges; propose the same default so
  setup's proposal and the evaluator's fallback never disagree.
- **`epic-integration` is not a configurable merge-policy key** (block-authoring.md:170-172). WHY:
  an epic-integration PR lands every child story's diff on `main` at once — always gated, never a
  policy choice, so setup must never present or write it as one.
- **`github-pipeline-config` lives only in `COMMANDS.md`, never atop `CLAUDE.md`**
  (SKILL.md:99-101, block-authoring.md:305-306). WHY: the header exists to explain the *dedicated
  config file's* markers; shoving it atop a human-facing `CLAUDE.md` the user already owns would be
  presumptuous noise, and a `CLAUDE.md`-resident header can't restrict itself to "these blocks" if
  the file also carries unrelated human content.
- **The illustrative `<!-- … -->` inside the header's own body text must stay an inline ellipsis, not
  a bare look-alike marker on its own line** (block-authoring.md:318-321). WHY: `config-block.sh`'s
  marker scan is a whole-line match — a stray look-alike on its own line would be picked up as a real
  (malformed) marker delimiter by the very script the header describes.
- **Preflight reports gaps; it never auto-fixes the environment** (SKILL.md:113-116, 337-338). WHY:
  logging in, installing tooling, or otherwise touching the user's machine is the user's call, not a
  silent side effect of "setting up config files" — conflating the two would make an unrelated
  destructive action reachable from a config-writing tool.
- **Runtime markers (`implementation-plan:v1`, `issue-research:v1`, the health-cache marker) are
  never touched by setup** (SKILL.md:107-109, 333-334). WHY: those are written by the pipeline
  *at use-time*, not configuration — setup editing them would corrupt live pipeline state it has no
  business touching.
- **Legacy migration removes the old block only after both replacements are written and confirmed**
  (block-authoring.md:396-399). WHY: restructures the user's declaration and infers prose that wasn't
  literally present before (per-target naming/fallbacks); removing the source before the split is
  confirmed would leave the repo with neither the old nor a working new configuration if the operator
  rejects the draft.
- **A validated worktree-lint failure or health-check dry-run failure is surfaced, not silently
  worked around** (SKILL.md:277, 287-288). WHY: a failing dry-run or a `MALFORMED_BLOCK`/dropped
  `would_run` entry means the block as written doesn't actually do what the operator thinks it does —
  the whole value of the offer-to-validate step is catching that gap before the resolver/evaluator
  trip on it in a live run.

## Sub-agents dispatched

None. `github-pipeline-setup` runs entirely in the main loop — SKILL.md never spawns an `Agent`/
`Explore` sub-agent by name; §3's repo scanning explicitly says to "use `Explore`/`Grep`/`Glob` for
this" (SKILL.md:159-160) as ordinary tool calls in the main session, not as a dispatched isolated
sub-agent with its own return contract (contrast with the resolver's state-distiller or the fitness
audit, which are named, isolated dispatches).

## Known bugs / gaps

- **Not actually a v1 bug — recorded to correct this spec's own S1 addendum.** `github-pipeline-setup`
  does **not** carry `disable-model-invocation: true` in its frontmatter (`skills/github-pipeline-setup/SKILL.md:1-6`
  shows only `name`, `model`, `effort`, `description`), and this is consistent with the rest of the
  repo's documentation, not a drift from it: `CLAUDE.md`'s "Four skills sit outside the pipeline
  conveyor" paragraph (root `CLAUDE.md:67-77`) names all four non-pipeline skills together in one
  sentence, but its `disable-model-invocation: true` parenthetical (`CLAUDE.md:73`) explicitly lists
  only `doc-reviewer`, `open-questions`, and `question-resolver` — `github-pipeline-setup` is
  deliberately absent from that list, and its frontmatter matches. This spec's own S1 addendum
  ("Emphasis for this spec" — note `disable-model-invocation: true` (frontmatter)) is therefore
  the party in error, not v1: it over-generalized the shared "standalone tool" framing to a specific
  frontmatter key setup doesn't have and was never claimed to have. Flagged for the reviewer per the
  brief's instruction to note where a source (here, the brief itself) turned out ambiguous or wrong,
  rather than silently perpetuating the error into the spec body — the spec's own "Overview" section
  above correctly states the frontmatter as read, not as the addendum characterized it.
- **v1 writes config-block changes in place, with no operator-gated "workspace + PR" landing step**
  (SKILL.md §5, "Write (and migrate legacy)" — writes directly via `config-block.sh upsert`/`remove`
  against the target file with no worktree/branch/PR involved anywhere in the skill). This is a
  known, deliberate v1→v2 delta, not a bug in v1's own terms: prd.md §8.2 requires all tracked-file
  changes (including "configuration blocks") to land via a workspace + an operator-gated final
  landing offer (commit + push + PR, or no-op on decline), and names `setup` explicitly as one of the
  three standalone tools that must move to that model. v1 has no workspace concept at all — it edits
  `COMMANDS.md`/`CLAUDE.md` directly in whatever the operator's actual working directory is at
  invocation time. Recorded here as a falsifiable parity-boundary fact for the cutover step: v2's
  `setup` must add the stage-in-workspace + offer-to-land gate that v1 does not have, per prd.md
  §6.1/§8.2 — this is an intentional behavior change, not something v1's own spec is defective for
  lacking.
- **The `pr-evaluator-health-checks` legacy migration path assumes the legacy block is a flat,
  unlabelled command list** (block-authoring.md:385-399) with no documented handling for a legacy
  block that already contains structured sub-sections or comments — the split logic ("static-looking
  commands" vs "the test invocation") is a judgment call with no worked example of an ambiguous case
  (e.g. a legacy block mixing three static commands and two different test invocations for two
  targets). Not a confirmed defect, but the spec text gives no disambiguation rule beyond "interview
  the user," so a mixed/multi-target legacy block's split outcome is under-specified in v1.
