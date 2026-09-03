## Approach
The #185 shape (issue #45): a plan that inserted work between a shipped prefix and an unshipped
tail by letter-suffixing the label instead of renumbering. Phases 1-2 are clean; the third entry
heads `3. **Phase 2c — ...**`, which `_PHASE_HEAD_RE` does not recognize as a head at all — so it
reads as a stray line inside phase 2 and the section fails at that line. The tail then compounds
it with prose inside a `closes-dod:` value and `depends-on: 2c`. This is the shape that reached
GitHub, passed a semantic plan review, and deadlocked the resolver two stages later.

## Phases
1. **Phase 1 — substrate**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: (none)
   - deliverable: the host substrate
   - depends-on: (none)
2. **Phase 2 — the login screen**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 1, 2
   - deliverable: the sole-factor login screen
   - depends-on: 1
3. **Phase 2c — `/auth` rebuilt, and the mutation-options gap closed**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: (none — it re-implements phase 2's 1 and 2 against the new client)
   - deliverable: the rebuilt `/auth` route
   - depends-on: 2
4. **Phase 3 — end-to-end proof**
   - kind: code-shipping
   - ships: PR commits to the issue branch
   - closes-dod: 3
   - deliverable: the end-to-end proof
   - depends-on: 2c
