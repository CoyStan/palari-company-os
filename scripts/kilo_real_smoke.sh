#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

allow_npx=()
if [[ "${PALARI_KILO_ALLOW_NPX:-0}" == "1" ]]; then
	allow_npx=(--allow-npx)
fi

timeout_args=()
if [[ -n "${PALARI_KILO_TIMEOUT:-}" ]]; then
	timeout_args=(--timeout "$PALARI_KILO_TIMEOUT")
fi

model_args=()
if [[ -n "${PALARI_KILO_MODEL:-}" ]]; then
	model_args=(--model "$PALARI_KILO_MODEL")
fi

agent_args=()
if [[ -n "${PALARI_KILO_AGENT:-}" ]]; then
	agent_args=(--agent "$PALARI_KILO_AGENT")
fi

message="${PALARI_KILO_SMOKE_MESSAGE:-Real Kilo smoke from Palari Company OS. Reply with a short summary and do not modify files.}"

printf 'Checking Kilo availability...\n'
./bin/palari kilo status "${allow_npx[@]}"

printf '\nPreviewing bounded Kilo prompt...\n'
./bin/palari kilo run WORK-0001 \
	--message "$message" \
	--dir "$repo_dir" \
	"${allow_npx[@]}" \
	"${timeout_args[@]}" \
	"${model_args[@]}" \
	"${agent_args[@]}"

if [[ "${PALARI_KILO_SMOKE_EXECUTE:-0}" != "1" ]]; then
	printf '\nNot executing Kilo. Set PALARI_KILO_SMOKE_EXECUTE=1 to run the real CLI.\n'
	exit 0
fi

printf '\nExecuting real Kilo CLI...\n'
./bin/palari kilo run WORK-0001 \
	--message "$message" \
	--dir "$repo_dir" \
	"${allow_npx[@]}" \
	"${timeout_args[@]}" \
	"${model_args[@]}" \
	"${agent_args[@]}" \
	--execute
