## Approach
Adversarial mutation: phase numbers skip from 1 straight to 3 (Phase 2 is missing), a renumbering
slip the resolver's `## Phases` parsing must never silently tolerate.

## Phases
1. **Phase 1 — substrate**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: (none)
   - deliverable: the shared parsing helper other phases build on
   - depends-on: (none)
3. **Phase 3 — decision write-up**
   - kind: decision-only
   - ships: external follow-up issue
   - closes-dod: (none)
   - deliverable: a filed follow-up issue capturing the open architectural question
   - depends-on: 1
