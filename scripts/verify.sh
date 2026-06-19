#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

python3 -m unittest discover -s tests
python3 scripts/check_style.py
python3 -m compileall -q src
python3 -m json.tool examples/acme-company-os/workspace.json >/tmp/palari-company-workspace-json-check.json
python3 -m json.tool workspaces/palari-company-os/workspace.json >/tmp/palari-company-dogfood-workspace-json-check.json
python3 -m json.tool schemas/workspace.schema.json >/tmp/palari-company-schema-json-check.json

./bin/palari validate --json >/tmp/palari-company-validate.json
./bin/palari --workspace workspaces/palari-company-os validate --json >/tmp/palari-company-dogfood-validate.json
./bin/palari state --json >/tmp/palari-company-state.json
./bin/palari --workspace workspaces/palari-company-os state --json >/tmp/palari-company-dogfood-state.json
./bin/palari queue --json >/tmp/palari-company-queue.json
./bin/palari --workspace workspaces/palari-company-os queue --json >/tmp/palari-company-dogfood-queue.json
./bin/palari detail WORK-0001 --json >/tmp/palari-company-detail-work-0001.json
./bin/palari --workspace workspaces/palari-company-os detail WORK-REPO-0001 --json >/tmp/palari-company-dogfood-detail-work-repo-0001.json
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json --json >/tmp/palari-company-scope-allowed.json
./bin/palari scope WORK-0001 --changed secrets.env --action deploy --json >/tmp/palari-company-scope-blocked.json
./bin/palari history --json >/tmp/palari-company-history.json
./bin/palari --workspace workspaces/palari-company-os history --json >/tmp/palari-company-dogfood-history.json
./bin/palari maintainer status --json >/tmp/palari-company-maintainer-status.json
rm -rf /tmp/palari-company-dashboard-acme /tmp/palari-company-dashboard-dogfood
./bin/palari --workspace examples/acme-company-os dashboard --out /tmp/palari-company-dashboard-acme --json >/tmp/palari-company-dashboard-acme.json
./bin/palari --workspace workspaces/palari-company-os dashboard --out /tmp/palari-company-dashboard-dogfood --json >/tmp/palari-company-dashboard-dogfood.json
grep -q 'id="queue"' /tmp/palari-company-dashboard-acme/index.html
grep -q 'id="work"' /tmp/palari-company-dashboard-acme/index.html
grep -q 'id="trust"' /tmp/palari-company-dashboard-acme/index.html
grep -q 'id="history"' /tmp/palari-company-dashboard-acme/index.html
grep -q 'id="authority"' /tmp/palari-company-dashboard-acme/index.html
grep -q 'RECEIPT-0001' /tmp/palari-company-dashboard-acme/index.html
grep -q 'No receipts recorded yet.' /tmp/palari-company-dashboard-dogfood/index.html

printf 'Palari Company OS verification passed.\n'
