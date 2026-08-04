## Approach
Adversarial mutation: Phase 1's `sub-issue:` value is `#0`. Issue numbers start at 1, so `#0` matches
the reference shape but can never name a real sub-issue — a placeholder that would otherwise diff as
a dangling reference on every run.

## Phases
1. **Phase 1 — writer core**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 1
   - deliverable: the export writer producing a well-formed file
   - depends-on: (none)
   - sub-issue: #0
