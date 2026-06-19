#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

python3 -m unittest discover -s tests
python3 scripts/check_style.py
python3 -m compileall -q src
python3 -m json.tool examples/acme-company-os/workspace.json >/tmp/palari-company-workspace-json-check.json
python3 -m json.tool schemas/workspace.schema.json >/tmp/palari-company-schema-json-check.json

./bin/palari validate --json >/tmp/palari-company-validate.json
./bin/palari state --json >/tmp/palari-company-state.json
./bin/palari queue --json >/tmp/palari-company-queue.json
./bin/palari detail WORK-0001 --json >/tmp/palari-company-detail-work-0001.json
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json --json >/tmp/palari-company-scope-allowed.json
./bin/palari scope WORK-0001 --changed secrets.env --action deploy --json >/tmp/palari-company-scope-blocked.json
./bin/palari maintainer status --json >/tmp/palari-company-maintainer-status.json

printf 'Palari Company OS verification passed.\n'
