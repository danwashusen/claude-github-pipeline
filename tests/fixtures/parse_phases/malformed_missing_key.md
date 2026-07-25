## Approach
Adversarial mutation: Phase 1 is missing its required `deliverable:` key entirely.

## Phases
1. **Phase 1 — substrate**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: (none)
   - depends-on: (none)
2. **Phase 2 — harness**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 1
   - deliverable: the measurement harness wired into CI
   - depends-on: 1
