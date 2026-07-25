## Approach
Adversarial mutation: Phase 1's `closes-dod:` value is neither the literal `(none)` nor a
well-formed comma-separated list of 1-based ints — a stray non-numeric reference.

## Phases
1. **Phase 1 — substrate**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: TBD
   - deliverable: the shared parsing helper other phases build on
   - depends-on: (none)
