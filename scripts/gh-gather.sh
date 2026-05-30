#!/usr/bin/env bash
#
# gh-gather.sh — the fixed three-call issue fetch envelope used by the
# github-* skills, collapsed into one deterministic JSON object so github-ops
# spends one round-trip instead of three. Pure mechanism: no judgment, no
# summarization. Bodies and threads come back verbatim from `gh`.
#
# Usage: gh-gather.sh <issue-number> <owner/repo> [marker-prefix]
#
# Output (stdout): a single JSON object
#   { "issue": <gh issue view json>,
#     "marker_comment": { "id", "url", "body" } | null,
#     "marker_comment_count": <int>,        # >1 means the caller must disambiguate
#     "open_prs": [ ... ] }
#
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "usage: gh-gather.sh <issue-number> <owner/repo> [marker-prefix]" >&2
  exit 2
fi

ISSUE="$1"
REPO="$2"
MARKER="${3:-}"

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
