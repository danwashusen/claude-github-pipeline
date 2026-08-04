## Approach
Adversarial mutation: Phase 1's `sub-issue:` key is present with an empty value. An empty value is
not the same as an absent key (unmapped) and not the same as `(none)` (an explicit substrate claim) —
it is an unfinished edit, so it must raise rather than collapse into either meaning.

## Phases
1. **Phase 1 — writer core**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 1
   - deliverable: the export writer producing a well-formed file
   - depends-on: (none)
   - sub-issue:
