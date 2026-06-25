#!/usr/bin/env bash
#
# worktree-hooks.sh — run a consuming repo's per-worktree lifecycle commands
# (the `<!-- worktree-setup -->` / `<!-- worktree-teardown -->` marker blocks) as
# one mechanical executor, so the resolver/evaluator skill bodies don't each
# re-implement the discover → parse → cd → run → report loop inline.
#
# This is the worktree-lifecycle analogue of gh-persist.sh: one self-contained
# script, a leading subcommand, judgment-free. It does NOT create or remove the
# worktree — those cwd-stateful git ops stay in the calling skill's main loop.
# It only runs the project-declared commands inside an already-existing worktree.
# The contract this enforces is documented in skills/_shared/worktree-lifecycle.md.
#
# Usage:
#   worktree-hooks.sh setup    <worktree_path> <repo_root> [--reused] [--dry-run]
#   worktree-hooks.sh teardown <worktree_path> <repo_root>            [--dry-run]
#   worktree-hooks.sh lint     <setup|teardown> <repo_root>
#
# Discovery: scans <repo_root>/COMMANDS.md and <repo_root>/CLAUDE.md, plus any
# file @-included (one level) from either, for the phase's marker block:
#   <!-- worktree-setup -->     …    <!-- /worktree-setup -->
#   <!-- worktree-teardown -->  …    <!-- /worktree-teardown -->
# Each block is a Markdown list; every item is `- ` + a backtick-quoted command +
# ` — <description>`. The backtick command is extracted; the description is
# ignored. The first candidate file with a non-empty block wins. No block (or an
# empty one) → clean no-op.
#
# Run policy:
#   setup    — FAIL-FAST. Stop on the first non-zero exit; overall exit 1.
#   teardown — BEST-EFFORT. Log each failure, continue; overall exit 0 always.
# Every command runs from inside <worktree_path> (the script cd's there), in
# declaration order. On a command failure the last 50 lines of its combined
# stdout+stderr are captured as the output tail.
#
# lint is parse-only: it discovers and parses the phase's block and lists the
# commands it would run, WITHOUT a worktree and WITHOUT running anything (no cd,
# no eval, no side effects). `github-pipeline-setup` uses it after writing a block
# to verify the final form parses to exactly the commands the operator approved —
# a command missing or truncated from `would_run` is the parser constraint biting
# (single backtick span per line, no embedded backticks).
#
# Human-readable progress (the status-line announcements) streams to stderr; the
# machine-readable result is a single JSON object on stdout:
#   { "op": "setup|teardown",
#     "phase_present": true|false,    # was a marker block found?
#     "commands_run": <int>,
#     "succeeded": true|false,        # setup: all passed; teardown: always true
#     "dry_run": true|false,
#     "reused": true|false,           # setup only
#     "first_failure": { "step", "command", "output_tail" },  # setup, on failure
#     "failures": [ { "step", "command", "output_tail" }, … ], # teardown, may be []
#     "would_run": [ "<cmd>", … ]     # only with --dry-run
#   }
# lint emits a distinct shape:
#   { "op": "lint",
#     "phase": "setup|teardown",
#     "phase_present": true|false,
#     "command_count": <int>,
#     "would_run": [ "<cmd>", … ] }
#
# Exit codes:
#   0  success (setup: all commands passed or no block; teardown: always; lint: always)
#   1  setup: a command exited non-zero (first_failure populated)
#   2  usage error / worktree or repo-root path not found / malformed marker block
#
# The script is a dumb deterministic executor. Idempotency of the commands
# themselves is the consuming repo's responsibility (see
# skills/_shared/worktree-lifecycle.md) — setup may re-run on a reused worktree,
# teardown on a half-provisioned one.

set -euo pipefail

die_usage() {
  echo "usage:" >&2
  echo "  worktree-hooks.sh setup    <worktree_path> <repo_root> [--reused] [--dry-run]" >&2
  echo "  worktree-hooks.sh teardown <worktree_path> <repo_root>            [--dry-run]" >&2
  echo "  worktree-hooks.sh lint     <setup|teardown> <repo_root>" >&2
  exit 2
}

# Print @-included paths (one level) found in a file. Matches an @-prefixed token
# that looks like a file path (has a slash or a dotted extension), which skips
# @mentions like @anthropic. Existence is re-checked by the caller, so a stray
# match is harmless.
find_includes() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  grep -oE '@[A-Za-z0-9._/-]+' "$file" 2>/dev/null \
    | sed -E 's/^@//' \
    | grep -E '(/|\.[A-Za-z0-9]+$)' || true
}

# discover_and_parse <marker> <repo_root>
# Sets two globals for the caller: PHASE_PRESENT ("true"/"false") and the COMMANDS
# array (one backtick-quoted command per element). A malformed block exits 2.
# Per-file block extraction is delegated to config-block.sh (the pipeline's
# canonical marker reader) so the delimiter semantics match the rest of the
# pipeline — exact-line delimiters, and a duplicate/unterminated block is surfaced
# rather than silently skipped. The first candidate with a non-empty block wins.
discover_and_parse() {
  local marker="$1" repo_root="$2"
  local script_dir config_block
  script_dir="$(cd "$(dirname "$0")" && pwd)"
  config_block="$script_dir/config-block.sh"

  # Ordered candidate list: the two root config files, then any file they @-include.
  local candidates=("$repo_root/COMMANDS.md" "$repo_root/CLAUDE.md")
  local root_file inc
  for root_file in "$repo_root/COMMANDS.md" "$repo_root/CLAUDE.md"; do
    while IFS= read -r inc; do
      [[ -z "$inc" ]] && continue
      case "$inc" in
        /*) candidates+=("$inc") ;;
        *)  candidates+=("$repo_root/$inc") ;;
      esac
    done < <(find_includes "$root_file")
  done

  local block="" f rc out
  PHASE_PRESENT="false"
  for f in "${candidates[@]}"; do
    [[ -f "$f" ]] || continue
    rc=0
    out="$("$config_block" read "$f" "$marker" 2>/dev/null)" || rc=$?
    case "$rc" in
      0) block="$out"; PHASE_PRESENT="true"; break ;;
      3) ;;  # marker absent in this file — try the next candidate
      *) echo "MALFORMED_BLOCK: <!-- $marker --> in $f (config-block.sh read exit $rc)" >&2; exit 2 ;;
    esac
  done

  # Parse list items → one command per array element (the backtick-quoted span).
  COMMANDS=()
  local cmdline
  # shellcheck disable=SC2016  # \1 is a sed backreference; single quotes are intentional.
  while IFS= read -r cmdline; do
    [[ -n "$cmdline" ]] && COMMANDS+=("$cmdline")
  done < <(printf '%s\n' "$block" | sed -n 's/^[[:space:]]*-[[:space:]]*`\([^`]*\)`.*/\1/p')
}

# would_run_json <count> — emit the COMMANDS array as a JSON array (or [] if empty).
would_run_json() {
  local n="$1"
  if [[ "$n" -eq 0 ]]; then
    printf '[]'
  else
    printf '%s\n' "${COMMANDS[@]}" | jq -R . | jq -s .
  fi
}

run_phase() {
  local op="$1"; shift
  [[ $# -lt 2 ]] && die_usage
  local worktree_path="$1"; shift
  local repo_root="$1"; shift
  local dry_run="false" reused="false"
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dry-run) dry_run="true"; shift ;;
      --reused)  [[ "$op" == "setup" ]] || die_usage; reused="true"; shift ;;
      *) die_usage ;;
    esac
  done

  [[ -d "$worktree_path" ]] || { echo "WORKTREE_NOT_FOUND: $worktree_path" >&2; exit 2; }
  [[ -d "$repo_root" ]]     || { echo "REPO_ROOT_NOT_FOUND: $repo_root" >&2; exit 2; }

  discover_and_parse "worktree-$op" "$repo_root"
  local n="${#COMMANDS[@]}"

  # ---- run ----
  local succeeded="true" first_failure_json="" failures_json="[]" commands_run=0
  local i rc logf tail50 cmd
  if [[ "$dry_run" != "true" && "$n" -gt 0 ]]; then
    if [[ "$op" == "setup" ]]; then
      if [[ "$reused" == "true" ]]; then
        echo "Running worktree setup ($n command(s))… (worktree reused; setup is idempotent)" >&2
      else
        echo "Running worktree setup ($n command(s))…" >&2
      fi
    else
      echo "Running worktree teardown ($n command(s))…" >&2
    fi

    i=0
    for cmd in "${COMMANDS[@]}"; do
      i=$((i + 1))
      rc=0
      logf="$(mktemp)"
      ( cd "$worktree_path" || exit 97; eval "$cmd" ) >"$logf" 2>&1 || rc=$?
      commands_run=$((commands_run + 1))
      if [[ "$rc" -ne 0 ]]; then
        tail50="$(tail -n 50 "$logf")"
        rm -f "$logf"
        if [[ "$op" == "setup" ]]; then
          echo "Worktree setup failed at step $i: $cmd" >&2
          printf '%s\n' "$tail50" >&2
          succeeded="false"
          first_failure_json="$(jq -n \
            --argjson step "$i" --arg command "$cmd" --arg output_tail "$tail50" \
            '{step: $step, command: $command, output_tail: $output_tail}')"
          break
        else
          echo "Worktree teardown step $i failed: $cmd" >&2
          failures_json="$(printf '%s' "$failures_json" | jq \
            --argjson step "$i" --arg command "$cmd" --arg output_tail "$tail50" \
            '. + [{step: $step, command: $command, output_tail: $output_tail}]')"
        fi
      else
        rm -f "$logf"
      fi
    done

    if [[ "$op" == "setup" && "$succeeded" == "true" ]]; then
      echo "Worktree setup complete." >&2
    elif [[ "$op" == "teardown" ]]; then
      echo "Worktree teardown complete." >&2
    fi
  fi

  # ---- emit ----
  local would_run=""
  if [[ "$dry_run" == "true" ]]; then
    would_run="$(would_run_json "$n")"
  fi

  jq -n \
    --arg op "$op" \
    --argjson phase_present "$PHASE_PRESENT" \
    --argjson commands_run "$commands_run" \
    --argjson succeeded "$succeeded" \
    --argjson dry_run "$dry_run" \
    --argjson reused "$reused" \
    --argjson failures "$failures_json" \
    --arg first_failure "$first_failure_json" \
    --arg would_run "$would_run" \
    '
    { op: $op, phase_present: $phase_present, commands_run: $commands_run,
      succeeded: $succeeded, dry_run: $dry_run }
    + (if $op == "setup" then { reused: $reused } else {} end)
    + (if $op == "setup"
       then (if $first_failure == "" then {} else { first_failure: ($first_failure | fromjson) } end)
       else { failures: $failures } end)
    + (if $would_run == "" then {} else { would_run: ($would_run | fromjson) } end)
    '

  if [[ "$op" == "setup" && "$succeeded" != "true" ]]; then
    exit 1
  fi
  exit 0
}

run_lint() {
  [[ $# -lt 2 ]] && die_usage
  local phase="$1"; shift
  case "$phase" in setup|teardown) ;; *) die_usage ;; esac
  local repo_root="$1"; shift
  [[ $# -eq 0 ]] || die_usage   # lint takes no flags

  [[ -d "$repo_root" ]] || { echo "REPO_ROOT_NOT_FOUND: $repo_root" >&2; exit 2; }

  discover_and_parse "worktree-$phase" "$repo_root"
  local n="${#COMMANDS[@]}"

  jq -n \
    --arg phase "$phase" \
    --argjson phase_present "$PHASE_PRESENT" \
    --argjson command_count "$n" \
    --argjson would_run "$(would_run_json "$n")" \
    '{ op: "lint", phase: $phase, phase_present: $phase_present,
       command_count: $command_count, would_run: $would_run }'
  exit 0
}

# ---- dispatch ----

[[ $# -lt 1 ]] && die_usage
SUB="$1"; shift
case "$SUB" in
  setup|teardown) run_phase "$SUB" "$@" ;;
  lint)           run_lint "$@" ;;
  *) die_usage ;;
esac
