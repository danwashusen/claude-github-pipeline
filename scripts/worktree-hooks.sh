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
#
# Exit codes:
#   0  success (setup: all commands passed or no block; teardown: always)
#   1  setup: a command exited non-zero (first_failure populated)
#   2  usage error / worktree or repo-root path not found
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
  exit 2
}

[[ $# -lt 3 ]] && die_usage
OP="$1"; shift
case "$OP" in
  setup|teardown) ;;
  *) die_usage ;;
esac

WORKTREE_PATH="$1"; shift
REPO_ROOT="$1"; shift

DRY_RUN="false"
REUSED="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN="true"; shift ;;
    --reused)  [[ "$OP" == "setup" ]] || die_usage; REUSED="true"; shift ;;
    *) die_usage ;;
  esac
done

MARKER="worktree-$OP"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_BLOCK="$SCRIPT_DIR/config-block.sh"

[[ -d "$WORKTREE_PATH" ]] || { echo "WORKTREE_NOT_FOUND: $WORKTREE_PATH" >&2; exit 2; }
[[ -d "$REPO_ROOT" ]]     || { echo "REPO_ROOT_NOT_FOUND: $REPO_ROOT" >&2; exit 2; }

# ---- discovery ----

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

# Ordered candidate list: the two root config files, then any file they @-include.
CANDIDATES=("$REPO_ROOT/COMMANDS.md" "$REPO_ROOT/CLAUDE.md")
for root_file in "$REPO_ROOT/COMMANDS.md" "$REPO_ROOT/CLAUDE.md"; do
  while IFS= read -r inc; do
    [[ -z "$inc" ]] && continue
    case "$inc" in
      /*) CANDIDATES+=("$inc") ;;
      *)  CANDIDATES+=("$REPO_ROOT/$inc") ;;
    esac
  done < <(find_includes "$root_file")
done

# First candidate that declares the block wins. Per-file block extraction is
# delegated to config-block.sh (the pipeline's canonical marker reader) so the
# delimiter semantics match the rest of the pipeline — exact-line delimiters,
# and a duplicate/unterminated block is surfaced rather than silently skipped.
BLOCK=""
PHASE_PRESENT="false"
for f in "${CANDIDATES[@]}"; do
  [[ -f "$f" ]] || continue
  rc=0
  out="$("$CONFIG_BLOCK" read "$f" "$MARKER" 2>/dev/null)" || rc=$?
  case "$rc" in
    0) BLOCK="$out"; PHASE_PRESENT="true"; break ;;
    3) ;;  # marker absent in this file — try the next candidate
    *) echo "MALFORMED_BLOCK: <!-- $MARKER --> in $f (config-block.sh read exit $rc)" >&2; exit 2 ;;
  esac
done

# Parse list items → one command per array element (the backtick-quoted span).
COMMANDS=()
# shellcheck disable=SC2016  # \1 is a sed backreference; single quotes are intentional.
while IFS= read -r cmdline; do
  [[ -n "$cmdline" ]] && COMMANDS+=("$cmdline")
done < <(printf '%s\n' "$BLOCK" | sed -n 's/^[[:space:]]*-[[:space:]]*`\([^`]*\)`.*/\1/p')

N="${#COMMANDS[@]}"

# ---- run ----

SUCCEEDED="true"
FIRST_FAILURE_JSON=""
FAILURES_JSON="[]"
COMMANDS_RUN=0

if [[ "$DRY_RUN" != "true" && "$N" -gt 0 ]]; then
  if [[ "$OP" == "setup" ]]; then
    if [[ "$REUSED" == "true" ]]; then
      echo "Running worktree setup ($N command(s))… (worktree reused; setup is idempotent)" >&2
    else
      echo "Running worktree setup ($N command(s))…" >&2
    fi
  else
    echo "Running worktree teardown ($N command(s))…" >&2
  fi

  i=0
  for cmd in "${COMMANDS[@]}"; do
    i=$((i + 1))
    rc=0
    logf="$(mktemp)"
    ( cd "$WORKTREE_PATH" || exit 97; eval "$cmd" ) >"$logf" 2>&1 || rc=$?
    COMMANDS_RUN=$((COMMANDS_RUN + 1))
    if [[ "$rc" -ne 0 ]]; then
      tail50="$(tail -n 50 "$logf")"
      rm -f "$logf"
      if [[ "$OP" == "setup" ]]; then
        echo "Worktree setup failed at step $i: $cmd" >&2
        printf '%s\n' "$tail50" >&2
        SUCCEEDED="false"
        FIRST_FAILURE_JSON="$(jq -n \
          --argjson step "$i" --arg command "$cmd" --arg output_tail "$tail50" \
          '{step: $step, command: $command, output_tail: $output_tail}')"
        break
      else
        echo "Worktree teardown step $i failed: $cmd" >&2
        FAILURES_JSON="$(printf '%s' "$FAILURES_JSON" | jq \
          --argjson step "$i" --arg command "$cmd" --arg output_tail "$tail50" \
          '. + [{step: $step, command: $command, output_tail: $output_tail}]')"
      fi
    else
      rm -f "$logf"
    fi
  done

  if [[ "$OP" == "setup" && "$SUCCEEDED" == "true" ]]; then
    echo "Worktree setup complete." >&2
  elif [[ "$OP" == "teardown" ]]; then
    echo "Worktree teardown complete." >&2
  fi
fi

# ---- emit ----

WOULD_RUN_JSON=""
if [[ "$DRY_RUN" == "true" ]]; then
  if [[ "$N" -eq 0 ]]; then
    WOULD_RUN_JSON='[]'
  else
    WOULD_RUN_JSON="$(printf '%s\n' "${COMMANDS[@]}" | jq -R . | jq -s .)"
  fi
fi

jq -n \
  --arg op "$OP" \
  --argjson phase_present "$PHASE_PRESENT" \
  --argjson commands_run "$COMMANDS_RUN" \
  --argjson succeeded "$SUCCEEDED" \
  --argjson dry_run "$DRY_RUN" \
  --argjson reused "$REUSED" \
  --argjson failures "$FAILURES_JSON" \
  --arg first_failure "$FIRST_FAILURE_JSON" \
  --arg would_run "$WOULD_RUN_JSON" \
  '
  { op: $op, phase_present: $phase_present, commands_run: $commands_run,
    succeeded: $succeeded, dry_run: $dry_run }
  + (if $op == "setup" then { reused: $reused } else {} end)
  + (if $op == "setup"
     then (if $first_failure == "" then {} else { first_failure: ($first_failure | fromjson) } end)
     else { failures: $failures } end)
  + (if $would_run == "" then {} else { would_run: ($would_run | fromjson) } end)
  '

if [[ "$OP" == "setup" && "$SUCCEEDED" != "true" ]]; then
  exit 1
fi
exit 0
