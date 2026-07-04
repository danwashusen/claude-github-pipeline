## Approach
Adversarial mutation: the numbered-list ordinal (`2.`) disagrees with its own `**Phase 3 — ...**`
label — a hand-edit that renumbered the list position without updating the label, or vice versa.

## Phases
1. **Phase 1 — substrate**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: (none)
   - deliverable: the shared parsing helper other phases build on
   - depends-on: (none)
2. **Phase 3 — harness**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 1
   - deliverable: the measurement harness wired into CI
   - depends-on: 1
