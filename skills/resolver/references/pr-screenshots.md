# PR screenshots — showing the reviewer what changed on screen

Read at S5 when you stage a phase whose change a user sees ("Stage the PR, commit, then loop"), and
again at S5.2's PR write. A reviewer reading a diff can't see a layout, a new state or a reworded
error. A screenshot shows them in one look, and without one the evaluator and the human reviewer
either guess or have to check out the branch and run it. `gh_persist.py` uploads the files with the
write (`--attach`, gh >= 2.99), so the images sit in the PR body itself.

## 1. When

When the phase changes what a user sees: layout, copy, a new screen or state, an error or empty
state, a visual regression fix. Not for a refactor, a backend-only change or a test-only phase. When
unsure whether a change shows, capture it: a screenshot that shows nothing new costs the reviewer a
glance, and a missing one costs them a checkout.

## 2. Capture

Capture **each changed state** from the app running from `facts.workspace.path`, with whatever this
session has to drive it: the in-app browser for a web UI, a simulator or emulator for a mobile app,
the repo's own run skill. When the consuming repo's `CLAUDE.md` says how to capture (its stack
profile, or a line like "a PR that changes what a user sees carries screenshots"), that guidance wins.
Capture the after-state always. Add a before-state when the phase changes an existing screen and the
default branch is cheap to run. Save each file under `<facts.scratch>/shots/` with a name that says
the state (`phase-2-empty-list.png`), and no `#` in it: `FILE#ALT` reads a `#` as the start of the alt
text. gh uploads png, jpg, jpeg, gif, webp and svg, plus mp4, mov and webm for a flow a still can't
show. When nothing in the session can run or drive the app, capture nothing and add one line under
`## Screenshots`: `Not captured: <why>`. Never ask the operator to take them.

## 3. Reference them in the body

Add a `## Screenshots` section to the PR body. Write one `![<the state, in words>](<absolute path>)`
per file, labelled by phase on a multi-phase PR. The path must be the **same absolute path** you pass
to `--attach`: gh matches the body's reference to the file by exact string (a relative `./shot.png`
would stay a dangling link while gh appended the image at the end), so `gh_persist.py` refuses a
relative path. The alt text is what a screen reader and a failed load show, so describe the state
("Export button disabled while the report loads"), not the file.

## 4. Write

Pass one `--attach "<absolute path>"` per file on the S5.2 PR write: `create-pr` in fresh mode,
`edit-pr-body` in continue mode, where the phase appends its screenshots to the existing
`## Screenshots` section. The envelope tells you what happened:

- **`posted_body_path`**: the body GitHub now holds, with each reference rewritten to a
  `user-attachments` URL. Every later PR-body write this run restages from it (S6's restage rule),
  never from `pr.md`. Its local paths no longer resolve, and posting them again would break the
  images.
- **`ATTACH_PARTIAL`** notice: the PR was written and some files didn't upload (`attach_stderr` says
  which). Never re-run `create-pr`, because the PR exists. Restage from `posted_body_path`, keep the
  failed files' references, and re-attach only those files with `edit-pr-body`. A file that fails
  twice gets `Not captured: upload failed` instead.
- **`ATTACH_READBACK_UNAVAILABLE`** notice: the write landed but no `posted_body_path` came back.
  Re-run `prep_resolver.py <issue> <owner/repo> --refresh`. With the PR now open it is in continue
  mode, and `facts.tracker.body_path` is the body GitHub holds. Restage from that.
- **Exit 1 with stderr `ATTACH_UNSUPPORTED:`**: the installed gh predates `--attach`, and nothing was
  written. Replace the section's references with `Not captured: gh < 2.99 cannot attach files`, then
  re-run the same write without `--attach`.

The screenshots and `pr.posted.md` are staging files: phase-continuation's §5 cleanup deletes them
with `pr.md`.
