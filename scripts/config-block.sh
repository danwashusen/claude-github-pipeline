#!/usr/bin/env bash
#
# config-block.sh — deterministic, idempotent read/write of the marker-delimited
# configuration blocks the github-pipeline skills consume (e.g.
# `<!-- issue-resolver-fast-checks -->`…`<!-- /issue-resolver-fast-checks -->`).
#
# This is the single execution path for `github-pipeline-setup`. The whole point
# is to keep the idempotency guarantee in deterministic code rather than asking
# the model to land an in-place Edit byte-perfect on every re-run: `upsert`
# replaces the interior of an existing block or appends a fresh one in a *canonical*
# form, so re-running with the same body is a byte-level no-op (the file isn't even
# touched on disk). Mirrors the gh-persist.sh philosophy: stage the body to a file,
# pass the path, and trust the script — nothing re-serializes the body across the
# orchestrator → sub-agent prompt boundary.
#
# It does **no** GitHub or git I/O — it only edits local Markdown — so it is not
# `gh-`prefixed and is not routed through github-ops.
#
# Usage:
#   config-block.sh read   <file> <marker-name>                 # interior to stdout
#   config-block.sh list   <file>                               # `<status> <name>` lines
#   config-block.sh upsert <file> <marker-name> <body-path>  [--dry-run] [--prepend]
#   config-block.sh remove <file> <marker-name>              [--dry-run]
#
# `--prepend` (upsert only) places a *newly created* block at the top of the file
# instead of appending it; when the block already exists it is a no-op (the block
# is replaced in place, position unchanged), so re-running stays idempotent.
#
# <marker-name> is the bare name without the comment syntax — e.g.
#   `issue-resolver-fast-checks`, not `<!-- issue-resolver-fast-checks -->`.
# A block is the line `<!-- NAME -->`, its interior, and the line `<!-- /NAME -->`,
# each delimiter on its own line (leading/trailing whitespace tolerated).
#
# `list` reports every open delimiter found, one per line, as `<status> <name>`:
#   ok           well-formed block (matching close present)
#   open         open delimiter with no matching close (unterminated)
#   dup          the name's delimiter appears more than once (malformed)
# Use it to discover already-configured, legacy, and malformed blocks.
#
# Exit codes:
#   0   success
#   1   unexpected error
#   2   usage error
#   3   (read only) the named block is absent
#   4   the named marker appears more than once (duplicate — refuse to guess)
#   5   the named marker is unterminated / closes before it opens
#
# JSON envelope (stdout, single line) for `upsert` and `remove`:
#   { "op": "upsert|remove",
#     "marker": "<name>",
#     "file": "<path>",
#     "changed": true|false,        (false ⇒ already in the desired state)
#     "dry_run": true|false,
#     "body_bytes": <int>,          (upsert only)
#     "body_sha256": "<hex>"        (upsert only)
#   }
#
# `read` and `list` print raw text, not JSON, so the skill can capture a block's
# contents or the inventory directly.

set -euo pipefail

die_usage() {
  echo "usage:" >&2
  echo "  config-block.sh read   <file> <marker-name>" >&2
  echo "  config-block.sh list   <file>" >&2
  echo "  config-block.sh upsert <file> <marker-name> <body-path> [--dry-run] [--prepend]" >&2
  echo "  config-block.sh remove <file> <marker-name>             [--dry-run]" >&2
  exit 2
}

# Marker names are interpolated into awk as literal comparison strings (never as
# regex), but constrain them anyway so a stray name can't smuggle in comment
# syntax that would confuse the delimiter scan.
validate_name() {
  local name="$1"
  if [[ ! "$name" =~ ^[A-Za-z0-9:_-]+$ ]]; then
    echo "INVALID_MARKER_NAME: $name (allowed: A-Z a-z 0-9 : _ -)" >&2
    exit 2
  fi
}

# Shared awk preamble: trim() plus a scan that records, for the target marker,
# its open/close counts and first indices, while buffering every line.
# shellcheck disable=SC2016  # these are awk source, not shell — single quotes are intentional
AWK_SCAN='
function trim(s){ sub(/^[ \t]+/,"",s); sub(/[ \t]+$/,"",s); return s }
BEGIN{ openm="<!-- " name " -->"; closem="<!-- /" name " -->";
       n=0; oc=0; cc=0; oi=0; ci=0 }
{ n++; lines[n]=$0; t=trim($0);
  if(t==openm){ oc++; if(oi==0) oi=n }
  else if(t==closem){ cc++; if(ci==0) ci=n } }
'

# emit_body() streams the staged body file line-by-line, re-adding one newline per
# line. This canonicalizes whatever trailing-newline state the body file is in, so
# the append path and the replace path produce identical interior bytes.
# shellcheck disable=SC2016  # awk source, not shell
AWK_EMIT_BODY='
function emit_body(  line){ while((getline line < bodyfile) > 0) print line; close(bodyfile) }
'

run_read() {
  [[ $# -lt 2 ]] && die_usage
  local file="$1" name="$2"
  validate_name "$name"
  [[ -f "$file" ]] || exit 3
  local rc=0
  awk -v name="$name" "$AWK_SCAN"'
    END{
      if(oc==0) exit 3
      if(oc>1 || cc>1) exit 4
      if(oc!=cc || ci<oi) exit 5
      for(i=oi+1;i<=ci-1;i++) print lines[i]
    }' "$file" || rc=$?
  exit "$rc"
}

run_list() {
  [[ $# -lt 1 ]] && die_usage
  local file="$1"
  [[ -f "$file" ]] || exit 0   # no file ⇒ no blocks ⇒ empty inventory
  awk '
    function trim(s){ sub(/^[ \t]+/,"",s); sub(/[ \t]+$/,"",s); return s }
    {
      t=trim($0)
      if(t ~ /^<!-- \/?[A-Za-z0-9:_-]+ -->$/){
        nm=t; sub(/^<!-- \/?/,"",nm); sub(/ -->$/,"",nm)
        if(t ~ /^<!-- \//) cc[nm]++; else oc[nm]++
      }
    }
    END{
      for(nm in oc){
        if(oc[nm]>1) st="dup"; else if(cc[nm]>=1) st="ok"; else st="open"
        print st, nm
      }
    }' "$file"
}

# Compare awk output (in $tmp) against the original and emit the envelope. Writes
# $tmp over $file only when it differs and we're not in --dry-run, so an unchanged
# run leaves the file (and its mtime) untouched.
finish_write() {
  local op="$1" file="$2" name="$3" tmp="$4" dry_run="$5" body_path="${6:-}"
  local changed="true"
  if [[ -f "$file" ]] && cmp -s "$tmp" "$file"; then
    changed="false"
  fi
  if [[ "$changed" == "true" && "$dry_run" != "true" ]]; then
    mv "$tmp" "$file"
  else
    rm -f "$tmp"
  fi

  local extra='{}'
  if [[ "$op" == "upsert" ]]; then
    local bytes sha
    bytes="$(wc -c < "$body_path" | tr -d ' ')"
    sha="$(shasum -a 256 "$body_path" | awk '{print $1}')"
    extra="$(jq -n --argjson b "$bytes" --arg s "$sha" '{body_bytes:$b, body_sha256:$s}')"
  fi
  jq -nc \
    --arg op "$op" --arg marker "$name" --arg file "$file" \
    --argjson changed "$changed" --argjson dry_run "$dry_run" \
    --argjson extra "$extra" \
    '{op:$op, marker:$marker, file:$file, changed:$changed, dry_run:$dry_run} + $extra'
}

run_upsert() {
  [[ $# -lt 3 ]] && die_usage
  local file="$1" name="$2" body_path="$3"; shift 3
  local dry_run="false" prepend="false"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry_run="true"; shift ;;
      --prepend) prepend="true"; shift ;;
      *) die_usage ;;
    esac
  done
  validate_name "$name"
  if [[ ! -f "$body_path" ]]; then
    echo "MISSING_BODY_FILE: $body_path" >&2
    exit 2
  fi

  # Absent file is treated as empty input so upsert can create it from scratch.
  local input="$file"
  [[ -f "$file" ]] || input="/dev/null"

  local tmp; tmp="$(mktemp)"
  local rc=0
  awk -v name="$name" -v bodyfile="$body_path" -v prepend="$prepend" "$AWK_SCAN$AWK_EMIT_BODY"'
    END{
      if(oc>1 || cc>1) exit 4
      if(oc!=cc) exit 5
      if(oc==1){
        if(ci<oi) exit 5
        for(i=1;i<=oi;i++) print lines[i]   # up to and including the open delimiter
        emit_body()
        for(i=ci;i<=n;i++) print lines[i]    # the close delimiter onward
      } else if(prepend=="true"){
        print openm                              # new block at the top of the file
        emit_body()
        print closem
        if(n>0 && trim(lines[1])!="") print ""   # one blank line before existing content
        for(i=1;i<=n;i++) print lines[i]
      } else {
        for(i=1;i<=n;i++) print lines[i]
        if(n>0 && trim(lines[n])!="") print ""   # one blank line before a new block
        print openm
        emit_body()
        print closem
      }
    }' "$input" > "$tmp" || rc=$?
  if [[ "$rc" -ne 0 ]]; then
    rm -f "$tmp"
    exit "$rc"
  fi
  finish_write "upsert" "$file" "$name" "$tmp" "$dry_run" "$body_path"
}

run_remove() {
  [[ $# -lt 2 ]] && die_usage
  local file="$1" name="$2"; shift 2
  local dry_run="false"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry_run="true"; shift ;;
      *) die_usage ;;
    esac
  done
  validate_name "$name"
  if [[ ! -f "$file" ]]; then
    # Nothing to remove — report no-op without inventing a file.
    jq -nc --arg marker "$name" --arg file "$file" --argjson dry_run "$dry_run" \
      '{op:"remove", marker:$marker, file:$file, changed:false, dry_run:$dry_run}'
    return 0
  fi

  local tmp; tmp="$(mktemp)"
  local rc=0
  awk -v name="$name" "$AWK_SCAN"'
    END{
      if(oc==0){ for(i=1;i<=n;i++) print lines[i]; exit 0 }   # absent ⇒ unchanged
      if(oc>1 || cc>1) exit 4
      if(oc!=cc || ci<oi) exit 5
      ds=oi
      if(oi>1 && trim(lines[oi-1])=="") ds=oi-1   # also drop one blank line above
      for(i=1;i<=n;i++){ if(i>=ds && i<=ci) continue; print lines[i] }
    }' "$file" > "$tmp" || rc=$?
  if [[ "$rc" -ne 0 ]]; then
    rm -f "$tmp"
    exit "$rc"
  fi
  finish_write "remove" "$file" "$name" "$tmp" "$dry_run"
}

# ---- dispatch ----

[[ $# -lt 1 ]] && die_usage
SUB="$1"; shift
case "$SUB" in
  read)   run_read "$@" ;;
  list)   run_list "$@" ;;
  upsert) run_upsert "$@" ;;
  remove) run_remove "$@" ;;
  *) die_usage ;;
esac
