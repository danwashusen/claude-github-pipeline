## Approach
Adversarial mutation: Phase 1's `checkpoint:` value is a word outside the closed pair. A typo must
not read as either answer — `continue` on a phase the operator meant to review is the costly
misreading — so it raises rather than defaulting.

## Phases
1. **Phase 1 — session token check**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 1
   - deliverable: the session token validated before any request is served
   - depends-on: (none)
   - checkpoint: skip
2. **Phase 2 — writer core**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 2
   - deliverable: the export writer producing a well-formed file
   - depends-on: 1
