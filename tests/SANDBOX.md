# The sandbox repo

The sandbox is a real, disposable GitHub repository used **only** for live smoke and
[the parity protocol](../docs/implementation.md#the-parity-protocol) — comparing a v1 skill's
behavior against its v2 replacement on identical starting state. The
[offline harness](README.md) (`python3 tests/run.py`) never touches it: that suite is
network-free by construction (`tests/test_no_real_gh.py`), while every parity/smoke run against
this repo is a real `gh`/network operation, run manually or by an explicitly-authorized step —
never by `tests/run.py`.

This document is the recipe: exact creation command, exact seeding steps, and where the repo's
URL is recorded once it exists. It is **not** itself a script — the creation and seeding steps
below are ordinary `gh`/`git` commands meant to be read and run (or reviewed before running),
matching how [implementation.md's S2 DoD](../docs/implementation.md#s2--offline-test-harness)
describes this file: sufficient "to add a case / seed the sandbox / run on Linux without reading
harness source."

> **SANDBOX_REPO_URL: `https://github.com/danwashusen/gh-pipeline-sandbox`**
>
> The line above is the single source of truth for "does the sandbox exist yet, and where." It
> is a placeholder until an authorized step creates the repo and fills it in — no live GitHub
> write happens as part of authoring this document. Once filled, every parity run and live smoke
> in this project points at that URL rather than re-deriving it.

## What the sandbox must contain

Per [implementation.md's "The sandbox repo"](../docs/implementation.md#the-sandbox-repo) section,
seeded with:

- The pipeline labels: `epic`, `story`, `question`, `planned`, `researched`, and the
  `audience:*` namespace (at minimum `audience:business`, `audience:architect`,
  `audience:developer` — see [`skills/_shared/question-issue.md`](../skills/_shared/question-issue.md)
  for the full audience-label convention; more can be created on demand the same way).
- One **epic** issue with **two story** issues under it.
- One plain **bug** issue (no epic/story shape — exercises the standard/non-epic path).
- One **question** issue (the `question`-issue body schema —
  [`skills/_shared/question-issue.md`](../skills/_shared/question-issue.md)).
- Grounding docs: `docs/prd.md`, `docs/architecture.md` (any small, realistic stand-ins — the
  sandbox's own PRD/architecture, not this repo's; skills only need *something* at those paths to
  exercise the grounding-doc read path).
- The config marker blocks (`<!-- NAME -->` / interior / `<!-- /NAME -->`, see
  [`scripts/config-block.sh`](../scripts/config-block.sh)'s header for the canonical form) in the
  sandbox's own `CLAUDE.md`: `issue-resolver-test-target`, `issue-resolver-fast-checks`,
  `issue-resolver-canonical-suite`, `pr-evaluator-health-checks`, `pr-evaluator-static-checks`,
  `pr-evaluator-test-target`, `pr-evaluator-escalation-labels`, `pr-evaluator-merge-policy`,
  `drafter-open-question-markers`, `worktree-setup`, `worktree-teardown`. (`claude-code-stack-profile`
  is user-authored prose, not machine-parsed — seed a minimal one for realism but no parity check
  depends on its exact content.)
- A minimal CI workflow whose pass/fail is **controllable per branch** — e.g. it fails whenever a
  specific marker file is present in the branch (so a parity run can force red-CI and
  green-CI states on demand without depending on the sandbox's actual code compiling).

## Creating the repo

```bash
gh repo create <org-or-user>/gh-pipeline-sandbox --private \
  --description "Disposable sandbox for github-pipeline v2 parity/smoke runs — see tests/SANDBOX.md" \
  --clone
cd gh-pipeline-sandbox
```

Record the resulting URL (`gh repo view --json url -q .url`) in the `SANDBOX_REPO_URL:` line at
the top of this file — that edit is the only state this document tracks about the live repo.

## Seeding

Run every step below from inside the freshly cloned sandbox working directory. Each step is
independent and safe to re-run (label/create calls are idempotent via `|| true` where GitHub
would otherwise error on a duplicate).

### 1. Labels

```bash
gh label create "epic"       --description "Epic issue"                --color 5319E7 || true
gh label create "story"      --description "Story under an epic"       --color 5319E7 || true
gh label create "question"   --description "Open question for an operator" --color D876E3 || true
gh label create "planned"    --description "Has a verified implementation plan" --color 0E8A16 || true
gh label create "researched" --description "Has a research dossier"    --color 0E8A16 || true
gh label create "audience:business"   --description "Question for business stakeholders" --color BFD4F2 || true
gh label create "audience:architect"  --description "Question for architecture review"   --color BFD4F2 || true
gh label create "audience:developer"  --description "Question for the implementing dev"  --color BFD4F2 || true
```

### 2. Grounding docs

```bash
mkdir -p docs
cat > docs/prd.md <<'EOF'
# gh-pipeline-sandbox — PRD (stand-in for parity runs)

A minimal product doc so grounding-doc reads have something real to load. Not the
github-pipeline project's own PRD — this is the *consuming repo's* doc, seeded fresh per sandbox.
EOF
cat > docs/architecture.md <<'EOF'
# gh-pipeline-sandbox — Architecture (stand-in for parity runs)

A minimal architecture doc so grounding-doc reads have something real to load.
EOF
git add docs/
git commit -m "seed: grounding docs for parity runs"
```

### 3. Config marker blocks

Append to (or create) `CLAUDE.md` in the sandbox root — each block is
`<!-- NAME -->` / interior / `<!-- /NAME -->`, one delimiter per line:

```bash
cat >> CLAUDE.md <<'EOF'

<!-- issue-resolver-test-target -->
python3 -m pytest -q
<!-- /issue-resolver-test-target -->

<!-- issue-resolver-fast-checks -->
python3 -m compileall -q .
<!-- /issue-resolver-fast-checks -->

<!-- issue-resolver-canonical-suite -->
python3 -m pytest
<!-- /issue-resolver-canonical-suite -->

<!-- pr-evaluator-health-checks -->
python3 -m compileall -q .
<!-- /pr-evaluator-health-checks -->

<!-- pr-evaluator-static-checks -->
python3 -m pyflakes .
<!-- /pr-evaluator-static-checks -->

<!-- pr-evaluator-test-target -->
python3 -m pytest -q
<!-- /pr-evaluator-test-target -->

<!-- pr-evaluator-escalation-labels -->
needs-human
<!-- /pr-evaluator-escalation-labels -->

<!-- pr-evaluator-merge-policy -->
standard: ask
epic: ask
story: ask
<!-- /pr-evaluator-merge-policy -->

<!-- drafter-open-question-markers -->
register: docs/open-questions.md
inline-pattern: \[OPEN QUESTION\]
open-status: unresolved
<!-- /drafter-open-question-markers -->

<!-- worktree-setup -->
echo "sandbox worktree setup ran"
<!-- /worktree-setup -->

<!-- worktree-teardown -->
echo "sandbox worktree teardown ran"
<!-- /worktree-teardown -->
EOF
git add CLAUDE.md
git commit -m "seed: config marker blocks for resolver/evaluator/drafter"
```

The block *contents* above are minimal placeholders — realistic enough to exercise the parse
path, not a claim about what a real consuming repo's checks should be. A parity run that needs a
specific block value (e.g. to force a fast-check failure) edits the relevant block on a throwaway
branch for that run.

### 4. Controllable CI workflow

```bash
mkdir -p .github/workflows
cat > .github/workflows/ci.yml <<'EOF'
name: sandbox-ci
on: [push, pull_request]
jobs:
  gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: fail if the red-CI marker file is present
        run: |
          if [ -f .ci-force-red ]; then
            echo "forced red: .ci-force-red is present on this branch"
            exit 1
          fi
          echo "ok"
EOF
git add .github/workflows/ci.yml
git commit -m "seed: controllable CI gate (fails when .ci-force-red is present)"
```

A parity run forces red CI on a branch with `touch .ci-force-red && git add -A && git commit -m
"force red" && git push`, and forces it back to green by removing that file — no dependency on
the sandbox's own code actually building or testing anything.

### 5. Epic + two stories

```bash
epic_num=$(gh issue create --title "Epic: sandbox parity fixture" \
  --label epic \
  --body $'## Summary\nParity-fixture epic with two stories.\n\n## Definition of done\n- [ ] Story A ships\n- [ ] Story B ships' \
  --json number -q .number 2>/dev/null || gh issue create --title "Epic: sandbox parity fixture" --label epic \
  --body $'## Summary\nParity-fixture epic with two stories.\n\n## Definition of done\n- [ ] Story A ships\n- [ ] Story B ships' | grep -oE '[0-9]+$')

gh issue create --title "Story A: first slice of the epic" \
  --label story \
  --body "## Summary
First story under epic #${epic_num}.

## Definition of done
- [ ] Slice A implemented"

gh issue create --title "Story B: second slice of the epic" \
  --label story \
  --body "## Summary
Second story under epic #${epic_num}.

## Definition of done
- [ ] Slice B implemented"
```

(`gh issue create`'s `--json` output flag support varies by `gh` version; the `||` fallback above
covers both. Confirm the printed issue numbers manually if scripting this non-interactively.)

### 6. Plain bug issue

```bash
gh issue create --title "Bug: sandbox fixture with no epic/story shape" \
  --body "## Summary
A standard bug report with no epic/story relationship — exercises the non-epic resolver/evaluator
path.

## Steps to reproduce
1. (fixture — not a real repro)

## Definition of done
- [ ] Root cause identified
- [ ] Fix implemented"
```

### 7. Question issue

Body schema per [`skills/_shared/question-issue.md`](../skills/_shared/question-issue.md):

```bash
gh issue create --title "Question: sandbox fixture question" \
  --label question --label "audience:architect" \
  --body '## Question
Should the sandbox fixture question resolve to option A or option B?

## Audience
Architecture review.

## Constraints
None — this is a fixture, not a real decision.

## Context
Seeded by tests/SANDBOX.md for parity/smoke runs exercising the question-pair skills.

## References
None.

## Why this matters
Exercises the question-issue read/decide/close path end-to-end.

## Tracked in
(seeded standalone — no doc back-link for this fixture)'
```

## Confirming the seed

```bash
gh label list
gh issue list --label epic
gh issue list --label story
gh issue list --label question
gh issue list --search "Bug: sandbox fixture"
gh api repos/{owner}/{repo}/contents/CLAUDE.md --jq .content | base64 -d | grep -c '<!--'
```

The last command should report the marker-block count (11 open + 11 close = 22 lines containing
`<!--`, i.e. 11 blocks) — a quick sanity check that the config seed step landed.

## Using the sandbox

- **Offline tests never touch it.** `python3 tests/run.py` has no code path that reads
  `SANDBOX_REPO_URL` or makes any network call — this is enforced, not just documented (see
  `tests/test_no_real_gh.py`).
- **Parity runs always do.** Each skill-cutover step's parity protocol
  ([implementation.md](../docs/implementation.md#the-parity-protocol)) constructs target state in
  this repo (or a twinned subtree of it for destructive/shared-parent flows), runs v1 then v2,
  and diffs the persisted artifacts.
- **Live smoke** (the read-only `gh_gather`/`gh_pr_gather` smoke mentioned in S21's Testing
  section, and any other explicitly-authorized read-only check) also targets this repo rather
  than a random real repo, so failures are reproducible against known seeded state.
- If a parity run needs a variant of the seeded state that isn't already here (e.g. an epic with
  three stories, or a PR against one of the stories), that variant is constructed **for the run**
  against this same repo and is not folded back into this seeding recipe unless a future step's
  DoD specifically calls for a new fixture shape — keep the base seed minimal and stable so
  parity runs have a consistent starting point to reset to.
