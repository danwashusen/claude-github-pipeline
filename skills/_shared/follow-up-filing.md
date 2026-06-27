# Follow-up filing — drafter-proxy sub-agent protocol

The single execution path for *creating* a follow-up issue from either the **resolver** (its §P5
review-loop and end-of-§10 checkpoint) or the **evaluator** (its post-merge residual-filing step).
Both file the same way: no hand-crafted `gh issue create` bodies — every follow-up routes through
`github-issue-drafter` (PRD-grounded, sub-agent-reviewed) via a `general-purpose` sub-agent that
proxy-confirms the draft and returns the URL. The caller keeps its own registry / timing / URL-weaving
rules; this file is only the filing round-trip they share.

## Protocol — sub-agent proxy-confirms via the drafter

For each item the user (resolver) or the evaluator has approved for filing, spawn a `general-purpose`
sub-agent with this prompt (substitute the placeholders at call time):

```
You are filing one GitHub follow-up issue on behalf of the calling skill
(github-issue-resolver or github-pr-evaluator). Invoke the
`github-issue-drafter` skill, proxy-confirm the draft, and return the
filed issue URL.

Item to file:
- Type: <bug | incomplete-feature | deferred-test | revise-existing>
- Title hint: <one-line summary>
- Description: <2–5 sentences explaining the follow-up>
- Parent reference: PR <URL>, issue #<N>, epic #<E> (if applicable)
- Repository: <owner/repo>

Steps:

1. Invoke the github-issue-drafter skill, passing the description above as
   the informal feedback. State the type hint, title hint, and parent
   reference clearly so the drafter has them at classification time.

2. The drafter will run its own sub-agent review loop (it validates against
   the project's PRD, architecture, constitution, and current code state).
   Let it complete its review-loop passes — don't try to shortcut them.

3. The drafter will reach its step-6 user-confirmation gate ("Show the
   draft and wait for confirmation"). You act as the user at this gate.
   Run three checks:

   a. Type — does the drafter's chosen type match the hint? If the drafter
      decided differently (e.g., classified as `incomplete-feature` when
      you hinted `bug`), accept the drafter's call IF its rationale is
      sound. The drafter sees the description directly and may classify
      better than the hint; only override if the drafter has clearly
      misread the description.

   b. Parent reference — is the parent PR/issue/epic preserved in the
      body's Related-issues section? The drafter's bug, story, feature,
      and incomplete-feature formats all have this section. Without it
      the filed issue is orphaned. If missing, reply to the drafter:
      "Please add the parent reference (PR <URL>, parent issue #<N>) to
      the Related-issues section."

   c. Substance — does the body's What's-wrong / What's-missing /
      Definition-of-done content match the description? If the drafter
      hallucinated detail the description doesn't support, reply with a
      one-sentence correction.

4. Approve if all three checks pass. If any check fails, reply with the
   correction and let the drafter iterate. Cap at 2 correction rounds —
   if the third draft still fails any check, stop and return an error to
   the parent with the latest draft inline so the parent can decide.

5. After approval, the drafter runs `gh issue create` (or `gh issue edit`
   in revise mode) and returns the URL. Capture that URL.

Return only:
- The filed URL (or "error: <reason>" if you stopped at step 4's cap)
- The drafter's final type (in case it overrode the hint)
- A one-line note if you raised any correction before approving

Do NOT file an issue yourself with `gh issue create`. The drafter does
this inside its own flow. Your role is to invoke, proxy-confirm, return.
```

The sub-agent isolates the drafter's verbose work (PRD reading, classification questioning, nested
sub-agent review loop) from the caller's main context. The caller sees one round-trip per item: input
brief → output URL.
