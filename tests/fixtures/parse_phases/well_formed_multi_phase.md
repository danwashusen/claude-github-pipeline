## Approach
A four-phase plan exercising all three phase kinds plus every field shape (the plan-schema.md
`## Phases` structured grammar — a distinct artifact from the PR-body `## Phase tracker`
checklist in `docs/specs/examples/phase-tracker.md`, which uses free-form phase labels for a
different purpose): a substrate phase that enables later work (`closes-dod: (none)`), a
code-shipping phase, an operator phase, and a decision-only phase, sequential and
depends-on-chained.

## Phases
1. **Phase 1 — substrate**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: (none)
   - deliverable: the shared parsing helper other phases build on
   - depends-on: (none)
2. **Phase 2 — harness**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 1, 2
   - deliverable: the measurement harness wired into CI
   - depends-on: 1
3. **Phase 3 — operator sign-off**
   - kind: operator
   - ships: comment on the issue
   - closes-dod: 3
   - deliverable: the operator's recorded go/no-go on the harness's first measurement run
   - depends-on: 2
4. **Phase 4 — decision write-up**
   - kind: decision-only
   - ships: external follow-up issue
   - closes-dod: (none)
   - deliverable: a filed follow-up issue capturing the open architectural question
   - depends-on: 3
