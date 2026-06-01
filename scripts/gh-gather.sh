#!/usr/bin/env bash
#
# gh-gather.sh — the fixed three-call issue fetch envelope used by the
# github-* skills, collapsed into one deterministic JSON object so github-ops
# spends one round-trip instead of three. Pure mechanism: no judgment, no
# summarization. Bodies and threads come back verbatim from `gh`.
#
# Usage: gh-gather.sh <issue-number> <owner/repo> [marker-prefix] [scratch-dir]
#
# When [scratch-dir] is omitted, output (stdout) is the legacy inline envelope:
#   { "issue": <gh issue view json>,
#     "marker_comment": { "id", "url", "body" } | null,
#     "marker_comment_count": <int>,        # >1 means the caller must disambiguate
#     "open_prs": [ ... ] }
#
# When [scratch-dir] is provided, the issue body + full comment thread + marker
# comment body are written through to files under that dir (never held in the
# agent's context), and the stdout envelope replaces the inline content with
# file paths + byte counts:
#   { number, title, state, labels, author, createdAt, updatedAt,
#     assignees, milestone, url,
#     issue_body_path, issue_body_bytes,
#     thread_path, thread_bytes, thread_comment_count,
#     marker_comment_present, marker_comment_id?, marker_comment_url?,
#     marker_comment_path?, marker_comment_bytes?,
#     marker_comment_count,
#     open_prs }
# Marker bodies can be very large (planner-authored implementation plans can
# exceed 25 KB), so they get the same write-through treatment as the issue body.
#
# The path-bearing mode is the recommended path for github-ops callers — the
# agent never has to Read large issue bodies/threads back to forward them.
#
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: gh-gather.sh <issue-number> <owner/repo> [marker-prefix] [scratch-dir]" >&2
  exit 2
fi

ISSUE="$1"
REPO="$2"
MARKER="${3:-}"
SCRATCH_DIR="${4:-}"

issue_json="$(gh issue view "$ISSUE" --repo "$REPO" --comments \
  --json number,title,body,state,labels,author,createdAt,updatedAt,comments,assignees,milestone,url)"

open_prs_json="$(gh pr list --repo "$REPO" --state open --search "$ISSUE in:body" \
  --json number,title,author,isDraft,headRefName,url,updatedAt)"

if [[ -n "$MARKER" ]]; then
  comments_json="$(gh api "repos/$REPO/issues/$ISSUE/comments" \
    --jq "[.[] | select(.body | startswith(\"$MARKER\")) | {id: .id, url: .html_url, body: .body}]")"
else
  comments_json="[]"
fi

if [[ -z "$SCRATCH_DIR" ]]; then
  # Legacy inline envelope — fully backward compatible with callers that
  # don't yet pass scratch_dir.
  jq -n \
    --argjson issue "$issue_json" \
    --argjson open_prs "$open_prs_json" \
    --argjson markers "$comments_json" \
    '{
       issue: $issue,
       marker_comment: ($markers | if length > 0 then .[0] else null end),
       marker_comment_count: ($markers | length),
       open_prs: $open_prs
     }'
  exit 0
fi

# Threshold-routed envelope: each verbatim section (body, thread, marker)
# stays inline as a JSON string field when its byte count is below the
# threshold and gets written through to a file under scratch_dir when above.
# This keeps small issues / small threads in `## RESULT` (no extra Read for
# the caller) while still routing large planner-authored marker comments,
# large bodies, and long threads through disk to avoid the harness spill.
THRESHOLD="${GH_OPS_INLINE_THRESHOLD_BYTES:-25000}"
mkdir -p "$SCRATCH_DIR"

# Extract each section's content into a shell variable.
body_str="$(printf '%s' "$issue_json" | jq -r '.body // ""')"
thread_str="$(printf '%s' "$issue_json" | jq -c '.comments')"
body_bytes="$(printf '%s' "$body_str" | wc -c | tr -d ' ')"
thread_bytes="$(printf '%s' "$thread_str" | wc -c | tr -d ' ')"
thread_comment_count="$(printf '%s' "$issue_json" | jq '.comments | length')"

# Body: inline if small, path if large.
if [[ "$body_bytes" -gt "$THRESHOLD" ]]; then
  body_path="$SCRATCH_DIR/issue-$ISSUE-body.md"
  printf '%s' "$body_str" > "$body_path"
  body_mode="path"
else
  body_path=""
  body_mode="inline"
fi

# Thread: same.
if [[ "$thread_bytes" -gt "$THRESHOLD" ]]; then
  thread_path="$SCRATCH_DIR/issue-$ISSUE-thread.json"
  printf '%s' "$thread_str" > "$thread_path"
  thread_mode="path"
else
  thread_path=""
  thread_mode="inline"
fi

# Marker comment body: written/inlined per the same threshold.
marker_count="$(printf '%s' "$comments_json" | jq 'length')"
if [[ "$marker_count" -gt 0 ]]; then
  marker_str="$(printf '%s' "$comments_json" | jq -r '.[0].body')"
  marker_id="$(printf '%s' "$comments_json" | jq -r '.[0].id')"
  marker_url="$(printf '%s' "$comments_json" | jq -r '.[0].url')"
  marker_bytes="$(printf '%s' "$marker_str" | wc -c | tr -d ' ')"
  if [[ "$marker_bytes" -gt "$THRESHOLD" ]]; then
    marker_path="$SCRATCH_DIR/issue-$ISSUE-marker.md"
    printf '%s' "$marker_str" > "$marker_path"
    marker_mode="path"
  else
    marker_path=""
    marker_mode="inline"
  fi
else
  marker_str=""
  marker_path=""
  marker_id=""
  marker_url=""
  marker_bytes=0
  marker_mode="absent"
fi

jq -n \
  --argjson issue "$issue_json" \
  --argjson open_prs "$open_prs_json" \
  --argjson marker_count "$marker_count" \
  --argjson threshold "$THRESHOLD" \
  --arg body_str "$body_str" \
  --arg body_path "$body_path" \
  --argjson body_bytes "$body_bytes" \
  --arg body_mode "$body_mode" \
  --arg thread_str "$thread_str" \
  --arg thread_path "$thread_path" \
  --argjson thread_bytes "$thread_bytes" \
  --argjson thread_comment_count "$thread_comment_count" \
  --arg thread_mode "$thread_mode" \
  --arg marker_str "$marker_str" \
  --arg marker_path "$marker_path" \
  --arg marker_id "$marker_id" \
  --arg marker_url "$marker_url" \
  --argjson marker_bytes "$marker_bytes" \
  --arg marker_mode "$marker_mode" \
  '{
     number: $issue.number,
     title: $issue.title,
     state: $issue.state,
     labels: $issue.labels,
     author: $issue.author,
     createdAt: $issue.createdAt,
     updatedAt: $issue.updatedAt,
     assignees: $issue.assignees,
     milestone: $issue.milestone,
     url: $issue.url,
     inline_threshold_bytes: $threshold,
     issue_body_bytes: $body_bytes,
     issue_body_mode: $body_mode,
     thread_bytes: $thread_bytes,
     thread_comment_count: $thread_comment_count,
     thread_mode: $thread_mode,
     marker_comment_present: ($marker_count > 0),
     marker_comment_count: $marker_count
   }
   + (if $body_mode == "inline"
      then { issue_body: $body_str }
      else { issue_body_path: $body_path } end)
   + (if $thread_mode == "inline"
      then { thread: ($thread_str | fromjson) }
      else { thread_path: $thread_path } end)
   + (if $marker_count > 0
      then {
        marker_comment_id: $marker_id,
        marker_comment_url: $marker_url,
        marker_comment_bytes: $marker_bytes,
        marker_comment_mode: $marker_mode
      } + (if $marker_mode == "inline"
           then { marker_comment_body: $marker_str }
           else { marker_comment_path: $marker_path } end)
      else {} end)
   + { open_prs: $open_prs }'
