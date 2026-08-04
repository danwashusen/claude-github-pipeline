## Approach
Adversarial mutation: Phase 1's `sub-issue:` value is a bare int. The `#` is required precisely so a
bare int can never be read as a DoD index or a phase number — accepting `214` here would make
`sub-issue: 3` ambiguous against `depends-on: 3`.

## Phases
1. **Phase 1 — writer core**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 1
   - deliverable: the export writer producing a well-formed file
   - depends-on: (none)
   - sub-issue: 214
