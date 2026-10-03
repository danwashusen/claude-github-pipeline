## Approach
Adversarial mutation: Phase 1's `checkpoint:` key is present with an empty value. An empty value is
not the same as an absent key (read as `pause`) — it is an unfinished edit, so it must raise rather
than collapse into either answer.

## Phases
1. **Phase 1 — rename the helper**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 1
   - deliverable: the parsing helper renamed across its call sites
   - depends-on: (none)
   - checkpoint:
2. **Phase 2 — writer core**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 2
   - deliverable: the export writer producing a well-formed file
   - depends-on: 1
