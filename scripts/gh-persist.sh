#!/usr/bin/env bash
#
# gh-persist.sh — single bundled execution path for the github-ops PERSIST
# operations (PERSIST_CREATE, PERSIST_BODY replace, PERSIST_COMMENT for all
# three targets). Mirrors the rule-7 pattern already in use for GATHER
# (gh-gather.sh, gh-pr-gather.sh): the sub-agent does not roll its own
# `mktemp + Write + test -s + gh …` ceremony; it shells out to this script
# and trusts the leading test-s gate.
#
# The body the script posts is the byte stream the *caller* already wrote
# to its scratch dir (the drafter's /tmp/gh-drafter-<slug>/story-N.md, the
# planner's /tmp/gh-planner-<N>/plan.md, etc.). Nothing re-serializes the
# body across the orchestrator → sub-agent prompt boundary, which is what
# the prior empty-body fix (08d2b93) failed to fully close — the in-agent
# Write tool / Bash race on the tmp file would land an empty body on the
# `gh issue create --body-file` call even when the body arrived intact in
# the prompt.
#
# Usage:
#   gh-persist.sh create     <repo> <body_path> --title <title> [--label L]… [--dry-run]
#   gh-persist.sh edit-body  <repo> <issue>     <body_path>                  [--dry-run]
#   gh-persist.sh comment    <repo> <target> <id> <body_path>
#                            [--review-action approve|comment|request-changes]
#                            [--delete-marker-id <id>]                        [--dry-run]
#
# <target> for `comment` is one of: issue | pr | pr-review.
# --review-action is required when target=pr-review and forbidden otherwise.
#
# Exit codes:
#   0   success — JSON envelope on stdout
#   1   gh error — gh's stderr is forwarded
#   2   usage error or empty/missing body file
#         (stderr line `EMPTY_BODY_FILE: <path>` for the empty/missing case
#          so github-ops can pattern-match it and return DECISION_NEEDED)
#
# JSON envelope (stdout, single line):
#   { "url": "<resulting url>",       (omitted in --dry-run)
#     "body_bytes": <int>,
#     "body_sha256": "<hex>",
#     "op": "create|edit-body|comment",
#     "dry_run": true|false,
#     "would_run": "<the gh command line>"  (only in --dry-run)
#   }
#
# The body_sha256 lets the caller verify byte-for-byte that the bytes the
# script saw match the bytes the caller staged — a stronger check than
# body_bytes alone, since two distinct bodies of the same length would
# pass a length check.

set -euo pipefail

die_usage() {
  echo "usage:" >&2
  echo "  gh-persist.sh create    <repo> <body_path> --title <title> [--label L]... [--dry-run]" >&2
  echo "  gh-persist.sh edit-body <repo> <issue>     <body_path>                    [--dry-run]" >&2
  echo "  gh-persist.sh comment   <repo> <target> <id> <body_path>" >&2
  echo "                          [--review-action approve|comment|request-changes]" >&2
  echo "                          [--delete-marker-id <id>]                          [--dry-run]" >&2
  exit 2
}

# Verify the caller-staged body file exists and is non-empty. This is the
# whole point of the script: the empty-body failure mode that bit #626/#627
# becomes unrepresentable here because the test runs *before* any gh call.
verify_body_file() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo "EMPTY_BODY_FILE: $path (not found)" >&2
    exit 2
  fi
  if [[ ! -s "$path" ]]; then
    echo "EMPTY_BODY_FILE: $path (zero bytes)" >&2
    exit 2
  fi
}

# Emit the JSON envelope. Args:
#   $1 op, $2 body_path, $3 dry_run (true|false), $4 url-or-empty,
#   $5 would_run-or-empty
emit_envelope() {
  local op="$1"
  local body_path="$2"
  local dry_run="$3"
  local url="$4"
  local would_run="$5"
  local bytes
  bytes="$(wc -c < "$body_path" | tr -d ' ')"
  local sha
  sha="$(shasum -a 256 "$body_path" | awk '{print $1}')"
  jq -n \
    --arg op "$op" \
    --argjson bytes "$bytes" \
    --arg sha "$sha" \
    --argjson dry_run "$dry_run" \
    --arg url "$url" \
    --arg would_run "$would_run" \
    '{
       op: $op,
       body_bytes: $bytes,
       body_sha256: $sha,
       dry_run: $dry_run
     }
     + (if $url == "" then {} else { url: $url } end)
     + (if $would_run == "" then {} else { would_run: $would_run } end)'
}

# Render a command-line for the dry-run preview. Shell-quotes each arg so
# the preview is faithfully reproducible.
quote_cmd() {
  local q=""
  local a
  for a in "$@"; do
    q+=" $(printf '%q' "$a")"
  done
  printf '%s' "${q# }"
}

cmd_create() {
  [[ $# -lt 2 ]] && die_usage
  local repo="$1"; shift
  local body_path="$1"; shift
  local title=""
  local -a labels=()
  local dry_run="false"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --title)    title="$2"; shift 2 ;;
      --label)    labels+=("$2"); shift 2 ;;
      --dry-run)  dry_run="true"; shift ;;
      *) die_usage ;;
    esac
  done
  [[ -z "$title" ]] && die_usage
  verify_body_file "$body_path"

  local -a cmd=(gh issue create --repo "$repo" --title "$title" --body-file "$body_path")
  local L
  for L in "${labels[@]+"${labels[@]}"}"; do
    cmd+=(--label "$L")
  done

  if [[ "$dry_run" == "true" ]]; then
    emit_envelope "create" "$body_path" true "" "$(quote_cmd "${cmd[@]}")"
    return 0
  fi
  local url
  url="$("${cmd[@]}")"
  emit_envelope "create" "$body_path" false "$url" ""
}

cmd_edit_body() {
  [[ $# -lt 3 ]] && die_usage
  local repo="$1"; shift
  local issue="$1"; shift
  local body_path="$1"; shift
  local dry_run="false"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry_run="true"; shift ;;
      *) die_usage ;;
    esac
  done
  verify_body_file "$body_path"

  local -a cmd=(gh issue edit "$issue" --repo "$repo" --body-file "$body_path")

  if [[ "$dry_run" == "true" ]]; then
    emit_envelope "edit-body" "$body_path" true "" "$(quote_cmd "${cmd[@]}")"
    return 0
  fi
  local url
  url="$("${cmd[@]}")"
  emit_envelope "edit-body" "$body_path" false "$url" ""
}

cmd_comment() {
  [[ $# -lt 4 ]] && die_usage
  local repo="$1"; shift
  local target="$1"; shift
  local id="$1"; shift
  local body_path="$1"; shift
  local review_action=""
  local delete_marker_id=""
  local dry_run="false"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --review-action)     review_action="$2"; shift 2 ;;
      --delete-marker-id)  delete_marker_id="$2"; shift 2 ;;
      --dry-run)           dry_run="true"; shift ;;
      *) die_usage ;;
    esac
  done
  verify_body_file "$body_path"

  case "$target" in
    issue|pr) [[ -n "$review_action" ]] && die_usage ;;
    pr-review) [[ -z "$review_action" ]] && die_usage ;;
    *) die_usage ;;
  esac

  # Optional marker delete (PR comments are issue comments under the hood,
  # so the issue-comments endpoint covers both).
  if [[ -n "$delete_marker_id" && "$dry_run" != "true" ]]; then
    local owner_name="$repo"
    gh api -X DELETE "repos/$owner_name/issues/comments/$delete_marker_id" >/dev/null
  fi

  local -a cmd
  case "$target" in
    issue)
      cmd=(gh issue comment "$id" --repo "$repo" --body-file "$body_path")
      ;;
    pr)
      cmd=(gh pr comment "$id" --repo "$repo" --body-file "$body_path")
      ;;
    pr-review)
      cmd=(gh pr review "$id" --repo "$repo" "--$review_action" --body-file "$body_path")
      ;;
  esac

  if [[ "$dry_run" == "true" ]]; then
    emit_envelope "comment" "$body_path" true "" "$(quote_cmd "${cmd[@]}")"
    return 0
  fi
  local url
  url="$("${cmd[@]}")"
  emit_envelope "comment" "$body_path" false "$url" ""
}

# ---- dispatch ----

[[ $# -lt 1 ]] && die_usage
SUB="$1"; shift
case "$SUB" in
  create)    cmd_create "$@" ;;
  edit-body) cmd_edit_body "$@" ;;
  comment)   cmd_comment "$@" ;;
  *) die_usage ;;
esac
