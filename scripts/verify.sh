#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
profile="${1:-complete}"

usage() {
  printf 'usage: ./scripts/verify.sh [complete|focused TEST_MODULE...]\n' >&2
}

if [[ "$profile" == "focused" ]]; then
  if [[ "$#" -lt 2 ]]; then
    usage
    exit 2
  fi
  shift
  exec python3 -S scripts/verification_profiles.py "$@"
fi
if [[ "$profile" != "complete" || "$#" -gt 1 ]]; then
  usage
  exit 2
fi

verify_output_dir="$(mktemp -d)"
trap 'rm -rf "$verify_output_dir"' EXIT

bash -n scripts/install_smoke.sh scripts/verify.sh scripts/make_demo_assets.sh
python3 -S scripts/check_style.py
ruff check .
mypy
python3 -S -m compileall -q src
python3 -S scripts/parallel_unittest.py
python3 -S -m json.tool examples/acme-company-os/workspace.json \
  >"$verify_output_dir/example-workspace.json"
python3 -S -m json.tool schemas/workspace.schema.json \
  >"$verify_output_dir/workspace-schema.json"
python3 -S -m json.tool spec/pcaw/v1/statement.schema.json \
  >"$verify_output_dir/pcaw-statement-schema.json"
python3 -S -m json.tool spec/pcaw/v1/verification-result.schema.json \
  >"$verify_output_dir/pcaw-report-schema.json"
python3 -S scripts/update_pcaw_tcb.py --check
python3 -S spec/pcaw/v1/conformance.py -- ./bin/palari proof verify
./bin/palari docs check --json >"$verify_output_dir/docs-check.json"
./scripts/install_smoke.sh

printf 'Palari Company OS candidate verification passed.\n'
