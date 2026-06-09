#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage:
  scripts/semble_refresh_search.sh search "query" [path] [top_k] [content]
  scripts/semble_refresh_search.sh find-related file_path line [path] [top_k] [content]

Defaults:
  path=.
  top_k=5
  content=code

Environment:
  SEMBLE_SKIP_UPGRADE=1  Skip automatic `uv tool install --upgrade "semble[mcp]"`.
  SEMBLE_BIN=/path/bin   Use a specific semble executable.
USAGE
}

die() {
  printf 'error: %s\n' "$1" >&2
  usage
  exit 64
}

validate_top_k() {
  local value="$1"
  [[ "$value" =~ ^[1-9][0-9]*$ ]] || die "top_k must be a positive integer"
}

validate_content() {
  local value="$1"
  case "$value" in
    code | docs | config | all) ;;
    *) die "content must be one of: code, docs, config, all" ;;
  esac
}

refresh_semble() {
  if [[ "${SEMBLE_SKIP_UPGRADE:-0}" == "1" || -n "${SEMBLE_BIN:-}" ]]; then
    return 0
  fi

  if command -v uv >/dev/null 2>&1; then
    uv tool install --upgrade "semble[mcp]" >&2
  fi
}

run_semble() {
  if [[ -n "${SEMBLE_BIN:-}" ]]; then
    "$SEMBLE_BIN" "$@"
    return
  fi

  if command -v semble >/dev/null 2>&1; then
    semble "$@"
    return
  fi

  if command -v uvx >/dev/null 2>&1; then
    uvx --from "semble[mcp]" semble "$@"
    return
  fi

  printf 'error: semble is not installed and uvx is unavailable\n' >&2
  exit 127
}

mode="${1:-}"
[[ -n "$mode" ]] || die "mode is required"

refresh_semble

case "$mode" in
  search)
    query="${2:-}"
    [[ -n "$query" ]] || die "search query is required"
    path="${3:-.}"
    top_k="${4:-5}"
    content="${5:-code}"
    validate_top_k "$top_k"
    validate_content "$content"
    run_semble search -k "$top_k" "$query" "$path" --content "$content"
    ;;
  find-related)
    file_path="${2:-}"
    line="${3:-}"
    [[ -n "$file_path" ]] || die "file_path is required"
    [[ -n "$line" ]] || die "line is required"
    [[ "$line" =~ ^[1-9][0-9]*$ ]] || die "line must be a positive integer"
    path="${4:-.}"
    top_k="${5:-5}"
    content="${6:-code}"
    validate_top_k "$top_k"
    validate_content "$content"
    run_semble find-related -k "$top_k" "$file_path" "$line" "$path" --content "$content"
    ;;
  *)
    die "unknown mode: $mode"
    ;;
esac
