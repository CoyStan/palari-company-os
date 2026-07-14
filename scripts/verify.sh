#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
profile="${1:-complete}"

if [[ "$profile" == "focused" || "$profile" == "affected" ]]; then
  exec python3 -S scripts/verification_profiles.py "$@"
fi
if [[ "$profile" != "complete" || "$#" -gt 1 ]]; then
  printf 'usage: ./scripts/verify.sh [complete|focused TEST_MODULE...|affected PATH... [--git-diff]]\n' >&2
  exit 2
fi

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
./bin/palari state --json >$verify_output_dir/palari-company-state.json
./bin/palari queue --json >$verify_output_dir/palari-company-queue.json
./bin/palari detail WORK-0001 --json >$verify_output_dir/palari-company-detail.json
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json --json >$verify_output_dir/palari-company-scope.json
./bin/palari history --json >$verify_output_dir/palari-company-history.json
./bin/palari maintainer status --json >$verify_output_dir/palari-company-maintainer-status.json
./bin/palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json >$verify_output_dir/palari-company-agent-brief-ready.json
./bin/palari --workspace examples/acme-company-os agent next --json >$verify_output_dir/palari-company-agent-next.json
./bin/palari docs check --json >$verify_output_dir/palari-company-docs-check.json
./bin/palari playbooks recommend WORK-0003 --json >$verify_output_dir/palari-company-playbooks.json
./bin/palari dashboard --out "$verify_output_dir/dashboard" --json >$verify_output_dir/palari-company-dashboard.json
./bin/palari desktop-prototype --out "$verify_output_dir/desktop" --json >$verify_output_dir/palari-company-desktop.json
./bin/palari --workspace workspaces/palari-company-os validate --json >$verify_output_dir/palari-company-dogfood-validate.json
./bin/palari --workspace workspaces/palari-company-os queue --json >$verify_output_dir/palari-company-dogfood-queue.json
./bin/palari --workspace workspaces/palari-company-os detail WORK-REPO-0001 --json >$verify_output_dir/palari-company-dogfood-detail.json
./bin/palari --workspace workspaces/palari-company-os history --json >$verify_output_dir/palari-company-dogfood-history.json
./bin/palari --workspace workspaces/palari-company-os linear doctor --json >$verify_output_dir/palari-company-linear-doctor.json
./bin/palari --workspace tests/fixtures/workspaces/split-workspace validate --json >$verify_output_dir/palari-company-split-validate.json
./bin/palari --workspace tests/fixtures/workspaces/split-workspace detail WORK-SPLIT --json >$verify_output_dir/palari-company-split-detail.json
./bin/palari demo --no-pause >$verify_output_dir/palari-company-demo.txt

printf 'Palari Company OS verification passed.\n'
