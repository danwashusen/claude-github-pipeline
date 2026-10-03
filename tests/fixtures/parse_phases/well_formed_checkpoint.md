## Approach
A four-phase plan exercising every `checkpoint:` shape: a mechanical phase the resolver may continue
past (`continue`), a phase whose change set wants a human look before the next phase builds on it
(`pause`), a phase with no `checkpoint:` line (a plan authored before the key, read as `pause`), and the
last code-shipping phase, which carries no key because it always hands off to the evaluator.

## Phases
1. **Phase 1 — rename the helper**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: (none)
   - deliverable: the parsing helper renamed across its call sites
   - depends-on: (none)
   - checkpoint: continue
2. **Phase 2 — session token check**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 1
   - deliverable: the session token validated before any request is served
   - depends-on: 1
   - checkpoint: pause
3. **Phase 3 — writer core**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 2
   - deliverable: the export writer producing a well-formed file
   - depends-on: 2
4. **Phase 4 — flag plumbing**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 3
   - deliverable: the command-line flag wired through to the writer
   - depends-on: 3
