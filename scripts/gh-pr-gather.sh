#!/usr/bin/env bash
#
# gh-pr-gather.sh — the bundled PR fetch envelope used by github-pr-evaluator
# and other github-* skills' GATHER_PR op. Mirrors gh-gather.sh's "one
# round-trip, not three" property for PRs and routes large outputs (diff,
# line-level review comments) through a scratch-dir so the github-ops agent
# never has to hold them in its own context.
#
# Usage:
#   gh-pr-gather.sh <pr-number> <owner/repo> [marker-prefix] [scratch-dir] \
#                   [--with-diff] [--with-line-comments]
#
# Required args: <pr-number>, <owner/repo>.
# Optional args (order-sensitive): [marker-prefix], [scratch-dir]; pass empty
# strings to skip while keeping later positional args.
# Flags: --with-diff and --with-line-comments are independent; either can be
# passed alone or together. When set, [scratch-dir] is REQUIRED (the script
# refuses to spill multi-KB outputs back through stdout).
#
# Output (stdout) is a single JSON envelope:
#   { pr metadata fields…,
#     closing_issues, status_check_rollup, headRefOid, mergeStateStatus,
#     mergeable, reviewDecision,
#     marker_comment, marker_comment_count,
#     diff_path?, diff_bytes?, diff_line_count?,
#     line_comments_path?, line_comments_bytes?, line_comments_count? }
# The optional fields are present only when their corresponding flag was set.
#
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: gh-pr-gather.sh <pr> <repo> [marker-prefix] [scratch-dir] [--with-diff] [--with-line-comments]" >&2
  exit 2
fi

PR="$1"
REPO="$2"
shift 2

MARKER=""
SCRATCH_DIR=""
WITH_DIFF=0
WITH_LINE_COMMENTS=0

# Optional positional args precede flags. Empty positional args are legal —
# allows the caller to pass an empty marker but still supply scratch_dir.
if [[ $# -gt 0 && "$1" != --* ]]; then MARKER="$1"; shift; fi
if [[ $# -gt 0 && "$1" != --* ]]; then SCRATCH_DIR="$1"; shift; fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-diff) WITH_DIFF=1; shift ;;
    --with-line-comments) WITH_LINE_COMMENTS=1; shift ;;
    *) echo "gh-pr-gather.sh: unknown arg '$1'" >&2; exit 2 ;;
  esac
done

if (( WITH_DIFF || WITH_LINE_COMMENTS )) && [[ -z "$SCRATCH_DIR" ]]; then
  echo "gh-pr-gather.sh: --with-diff / --with-line-comments require a scratch-dir" >&2
  exit 2
fi

if [[ -n "$SCRATCH_DIR" ]]; then
  mkdir -p "$SCRATCH_DIR"
fi

# Run the parallelisable fetches in the background, capturing each into a
# scratch file. Even when SCRATCH_DIR isn't passed we route stdout through
# a tmp area so the bash parent never holds them in a shell variable
# simultaneously (which would inflate memory for huge diffs).
tmp_root="$(mktemp -d "${TMPDIR:-/tmp}/gh-pr-gather.XXXXXX")"
trap 'rm -rf "$tmp_root"' EXIT

view_out="$tmp_root/view.json"
markers_out="$tmp_root/markers.json"

# 1. PR metadata + nested fields (one call covers everything except the diff
#    and the line-comments which use different endpoints).
( gh pr view "$PR" --repo "$REPO" \
    --json number,title,body,state,isDraft,author,baseRefName,headRefName,commits,additions,deletions,changedFiles,closingIssuesReferences,comments,reviews,latestReviews,reviewDecision,mergeStateStatus,mergeable,statusCheckRollup,headRefOid,url \
    > "$view_out" ) &
view_pid=$!

# 2. Marker comment lookup over the PR's issue-comments thread (PR comments
#    are issue comments under the hood, so the marker prefix lookup uses the
#    same endpoint shape as gh-gather.sh).
if [[ -n "$MARKER" ]]; then
  ( gh api "repos/$REPO/issues/$PR/comments" \
      --jq "[.[] | select(.body | startswith(\"$MARKER\")) | {id: .id, url: .html_url, body: .body}]" \
      > "$markers_out" ) &
  markers_pid=$!
else
  printf '%s' '[]' > "$markers_out"
  markers_pid=""
fi

# 3. PR diff — write through to scratch_dir directly. Never read back here.
if (( WITH_DIFF )); then
  diff_path="$SCRATCH_DIR/pr-$PR-diff.patch"
  ( gh pr diff "$PR" --repo "$REPO" > "$diff_path" ) &
  diff_pid=$!
else
  diff_pid=""
fi

# 4. Line-level review comments JSON — same treatment.
if (( WITH_LINE_COMMENTS )); then
  line_comments_path="$SCRATCH_DIR/pr-$PR-line-comments.json"
  ( gh api "repos/$REPO/pulls/$PR/comments" > "$line_comments_path" ) &
  line_comments_pid=$!
else
  line_comments_pid=""
fi

# Wait for each background job; any non-zero exit propagates.
wait "$view_pid"
[[ -n "$markers_pid" ]] && wait "$markers_pid"
[[ -n "$diff_pid" ]] && wait "$diff_pid"
[[ -n "$line_comments_pid" ]] && wait "$line_comments_pid"

# Assemble the envelope. The view JSON stays inline (it's metadata scalars
# plus the PR body, which is bounded — agents need it to read the body
# directly). The diff and line-comments are referenced by path only.
view_json="$(cat "$view_out")"
markers_json="$(cat "$markers_out")"

if (( WITH_DIFF )); then
  diff_bytes="$(wc -c < "$diff_path" | tr -d ' ')"
  diff_line_count="$(wc -l < "$diff_path" | tr -d ' ')"
else
  diff_bytes=0
  diff_line_count=0
fi

if (( WITH_LINE_COMMENTS )); then
  line_comments_bytes="$(wc -c < "$line_comments_path" | tr -d ' ')"
  line_comments_count="$(jq 'length' "$line_comments_path")"
else
  line_comments_bytes=0
  line_comments_count=0
fi

# When scratch_dir is set, route each verbatim section (body, thread,
# reviews, marker) through the inline-vs-path threshold so small payloads
# stay in `## RESULT` while large ones land on disk. The diff and the
# line-comments JSON ALWAYS go to disk when requested — they are the cases
# that triggered the original spill problem and there's no realistic small
# diff case worth inlining.
if [[ -n "$SCRATCH_DIR" ]]; then
  THRESHOLD="${GH_OPS_INLINE_THRESHOLD_BYTES:-25000}"

  body_str="$(printf '%s' "$view_json" | jq -r '.body // ""')"
  thread_str="$(printf '%s' "$view_json" | jq -c '.comments')"
  reviews_str="$(printf '%s' "$view_json" | jq -c '.reviews')"
  body_bytes="$(printf '%s' "$body_str" | wc -c | tr -d ' ')"
  thread_bytes="$(printf '%s' "$thread_str" | wc -c | tr -d ' ')"
  reviews_bytes="$(printf '%s' "$reviews_str" | wc -c | tr -d ' ')"
  thread_comment_count="$(printf '%s' "$view_json" | jq '.comments | length')"
  reviews_count="$(printf '%s' "$view_json" | jq '.reviews | length')"

  if [[ "$body_bytes" -gt "$THRESHOLD" ]]; then
    body_path="$SCRATCH_DIR/pr-$PR-body.md"
    printf '%s' "$body_str" > "$body_path"
    body_mode="path"
  else
    body_path=""; body_mode="inline"
  fi
  if [[ "$thread_bytes" -gt "$THRESHOLD" ]]; then
    thread_path="$SCRATCH_DIR/pr-$PR-thread.json"
    printf '%s' "$thread_str" > "$thread_path"
    thread_mode="path"
  else
    thread_path=""; thread_mode="inline"
  fi
  if [[ "$reviews_bytes" -gt "$THRESHOLD" ]]; then
    reviews_path="$SCRATCH_DIR/pr-$PR-reviews.json"
    printf '%s' "$reviews_str" > "$reviews_path"
    reviews_mode="path"
  else
    reviews_path=""; reviews_mode="inline"
  fi

  marker_count="$(printf '%s' "$markers_json" | jq 'length')"
  if [[ "$marker_count" -gt 0 ]]; then
    marker_str="$(printf '%s' "$markers_json" | jq -r '.[0].body')"
    marker_id="$(printf '%s' "$markers_json" | jq -r '.[0].id')"
    marker_url="$(printf '%s' "$markers_json" | jq -r '.[0].url')"
    marker_bytes="$(printf '%s' "$marker_str" | wc -c | tr -d ' ')"
    if [[ "$marker_bytes" -gt "$THRESHOLD" ]]; then
      marker_path="$SCRATCH_DIR/pr-$PR-marker.md"
      printf '%s' "$marker_str" > "$marker_path"
      marker_mode="path"
    else
      marker_path=""; marker_mode="inline"
    fi
  else
    marker_str=""; marker_path=""; marker_id=""; marker_url=""; marker_bytes=0; marker_mode="absent"
  fi

  jq -n \
    --argjson view "$view_json" \
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
    --arg reviews_str "$reviews_str" \
    --arg reviews_path "$reviews_path" \
    --argjson reviews_bytes "$reviews_bytes" \
    --argjson reviews_count "$reviews_count" \
    --arg reviews_mode "$reviews_mode" \
    --arg marker_str "$marker_str" \
    --arg marker_path "$marker_path" \
    --arg marker_id "$marker_id" \
    --arg marker_url "$marker_url" \
    --argjson marker_bytes "$marker_bytes" \
    --arg marker_mode "$marker_mode" \
    --arg diff_path "${diff_path:-}" \
    --argjson diff_bytes "$diff_bytes" \
    --argjson diff_line_count "$diff_line_count" \
    --arg line_comments_path "${line_comments_path:-}" \
    --argjson line_comments_bytes "$line_comments_bytes" \
    --argjson line_comments_count "$line_comments_count" \
    --argjson with_diff "$WITH_DIFF" \
    --argjson with_lc "$WITH_LINE_COMMENTS" \
    '{
       number: $view.number,
       title: $view.title,
       state: $view.state,
       isDraft: $view.isDraft,
       author: $view.author,
       baseRefName: $view.baseRefName,
       headRefName: $view.headRefName,
       headRefOid: $view.headRefOid,
       additions: $view.additions,
       deletions: $view.deletions,
       changedFiles: $view.changedFiles,
       commit_count: ($view.commits | length),
       mergeStateStatus: $view.mergeStateStatus,
       mergeable: $view.mergeable,
       reviewDecision: $view.reviewDecision,
       statusCheckRollup: $view.statusCheckRollup,
       closingIssuesReferences: $view.closingIssuesReferences,
       url: $view.url,
       latestReviews: $view.latestReviews,
       inline_threshold_bytes: $threshold,
       body_bytes: $body_bytes,
       body_mode: $body_mode,
       thread_bytes: $thread_bytes,
       thread_comment_count: $thread_comment_count,
       thread_mode: $thread_mode,
       reviews_bytes: $reviews_bytes,
       reviews_count: $reviews_count,
       reviews_mode: $reviews_mode,
       marker_comment_present: ($marker_count > 0),
       marker_comment_count: $marker_count
     }
     + (if $body_mode == "inline" then { body: $body_str } else { body_path: $body_path } end)
     + (if $thread_mode == "inline" then { thread: ($thread_str | fromjson) } else { thread_path: $thread_path } end)
     + (if $reviews_mode == "inline" then { reviews: ($reviews_str | fromjson) } else { reviews_path: $reviews_path } end)
     + (if $marker_count > 0
        then { marker_comment_id: $marker_id, marker_comment_url: $marker_url,
               marker_comment_bytes: $marker_bytes, marker_comment_mode: $marker_mode }
             + (if $marker_mode == "inline"
                then { marker_comment_body: $marker_str }
                else { marker_comment_path: $marker_path } end)
        else {} end)
     + (if $with_diff == 1
        then { diff_path: $diff_path, diff_bytes: $diff_bytes, diff_line_count: $diff_line_count }
        else {} end)
     + (if $with_lc == 1
        then { line_comments_path: $line_comments_path,
               line_comments_bytes: $line_comments_bytes,
               line_comments_count: $line_comments_count }
        else {} end)
    '
else
  # No-scratch-dir mode: legacy inline envelope (body, comments, reviews
  # inline). Diff and line-comments aren't supported without a scratch_dir —
  # the script already errored if those flags were passed.
  jq -n \
    --argjson view "$view_json" \
    --argjson markers "$markers_json" \
    '$view + {
       marker_comment: ($markers | if length > 0 then .[0] else null end),
       marker_comment_count: ($markers | length)
     }'
fi
