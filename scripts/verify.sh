#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
verify_output_dir="$(mktemp -d)"
trap 'rm -rf "$verify_output_dir"' EXIT

bash -n scripts/install_smoke.sh scripts/verify.sh scripts/make_demo_assets.sh
python3 -S -m unittest discover -s tests
python3 -S scripts/check_style.py
python3 -S -m compileall -q src
python3 -S -m json.tool examples/acme-company-os/workspace.json >$verify_output_dir/palari-company-workspace-json-check.json
python3 -S -m json.tool workspaces/palari-company-os/workspace.json >$verify_output_dir/palari-company-dogfood-workspace-json-check.json
python3 -S -m json.tool schemas/workspace.schema.json >$verify_output_dir/palari-company-schema-json-check.json

./bin/palari validate --json >$verify_output_dir/palari-company-validate.json
./bin/palari queue --json >$verify_output_dir/palari-company-queue.json
./bin/palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json >$verify_output_dir/palari-company-agent-brief-ready.json
./bin/palari docs check --json >$verify_output_dir/palari-company-docs-check.json
./bin/palari --workspace workspaces/palari-company-os linear doctor --json >$verify_output_dir/palari-company-linear-doctor.json
./bin/palari demo --no-pause >$verify_output_dir/palari-company-demo.txt

printf 'Palari Company OS verification passed.\n'
