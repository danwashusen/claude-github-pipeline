## Approach
Adversarial mutation: Phase 1's `sub-issue:` value is a comma-separated list. The phase-to-sub-issue
map is N:1 — several phases may serve one sub-issue, but a phase serves at most one — so a list is a
contract violation the parser must reject rather than silently narrow to its first item.

## Phases
1. **Phase 1 — writer core**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 1
   - deliverable: the export writer producing a well-formed file
   - depends-on: (none)
   - sub-issue: #214, #216
