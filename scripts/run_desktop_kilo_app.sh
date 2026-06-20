#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out_dir="${PALARI_DESKTOP_OUT:-/tmp/palari-desktop-prototype}"
host="${PALARI_DESKTOP_HOST:-127.0.0.1}"
port="${PALARI_DESKTOP_PORT:-0}"

args=(
	"$repo_dir/bin/palari"
	desktop-serve
	--out "$out_dir"
	--host "$host"
	--port "$port"
	--dir "$repo_dir"
)

if [[ "${PALARI_KILO_ALLOW_NPX:-0}" == "1" ]]; then
	args+=(--allow-npx)
fi

if [[ "${PALARI_KILO_ALLOW_EXECUTE:-0}" == "1" ]]; then
	args+=(--allow-kilo-execute)
fi

if [[ -n "${PALARI_KILO_MODEL:-}" ]]; then
	args+=(--model "$PALARI_KILO_MODEL")
fi

if [[ -n "${PALARI_KILO_AGENT:-}" ]]; then
	args+=(--agent "$PALARI_KILO_AGENT")
fi

if [[ -n "${PALARI_KILO_TIMEOUT:-}" ]]; then
	args+=(--timeout "$PALARI_KILO_TIMEOUT")
fi

printf 'Starting Palari Desktop Kilo app...\n'
printf 'Output: %s\n' "$out_dir"
printf 'Kilo execute: %s\n' "${PALARI_KILO_ALLOW_EXECUTE:-0}"
exec "${args[@]}"
