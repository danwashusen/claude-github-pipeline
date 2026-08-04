## Approach
A four-phase plan against a target that already has deliverable-slice sub-issues, exercising every
`sub-issue:` shape the N:1-and-total rule admits: a substrate phase claiming `(none)`, TWO phases
serving the SAME sub-issue (#214 — legal under N:1 and never a finding), and a third phase serving a
different one (#216). Coverage is total over the open set. Sequential and depends-on-chained.

## Phases
1. **Phase 1 — substrate**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: (none)
   - deliverable: the shared parsing helper other phases build on
   - depends-on: (none)
   - sub-issue: (none)
2. **Phase 2 — writer core**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 1
   - deliverable: the export writer producing a well-formed file
   - depends-on: 1
   - sub-issue: #214
3. **Phase 3 — writer polish**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 2
   - deliverable: the export writer's streaming path for large inputs
   - depends-on: 2
   - sub-issue: #214
4. **Phase 4 — flag plumbing**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 3
   - deliverable: the command-line flag wired through to the writer
   - depends-on: 3
   - sub-issue: #216
