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

bash -n scripts/install_smoke.sh scripts/verify.sh scripts/make_demo_assets.sh scripts/pcaw_demo.sh
python3 -S scripts/parallel_unittest.py
python3 -S scripts/check_style.py
python3 -S -m compileall -q src
python3 -S -m json.tool examples/acme-company-os/workspace.json >$verify_output_dir/palari-company-workspace-json-check.json
python3 -S -m json.tool workspaces/palari-company-os/workspace.json >$verify_output_dir/palari-company-dogfood-workspace-json-check.json
python3 -S -m json.tool schemas/workspace.schema.json >$verify_output_dir/palari-company-schema-json-check.json
python3 -S -m json.tool spec/pcaw/v1/statement.schema.json >$verify_output_dir/pcaw-statement-schema.json
python3 -S -m json.tool spec/pcaw/v1/verification-result.schema.json >$verify_output_dir/pcaw-report-schema.json
python3 -S scripts/update_pcaw_tcb.py --check
python3 -S spec/pcaw/v1/conformance.py -- ./bin/palari proof verify

# These smokes are read-only and write only to distinct output paths. Running
# them concurrently preserves every check while avoiding repeated interpreter
# startup on the complete gate's critical path.
smoke_pids=()
run_smoke() {
  "$@" &
  smoke_pids+=("$!")
}

run_smoke ./bin/palari validate --json >$verify_output_dir/palari-company-validate.json
run_smoke ./bin/palari state --json >$verify_output_dir/palari-company-state.json
run_smoke ./bin/palari queue --json >$verify_output_dir/palari-company-queue.json
run_smoke ./bin/palari detail WORK-0001 --json >$verify_output_dir/palari-company-detail.json
run_smoke ./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json --json >$verify_output_dir/palari-company-scope.json
run_smoke ./bin/palari history --json >$verify_output_dir/palari-company-history.json
run_smoke ./bin/palari maintainer status --json >$verify_output_dir/palari-company-maintainer-status.json
run_smoke ./bin/palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json >$verify_output_dir/palari-company-agent-brief-ready.json
run_smoke ./bin/palari --workspace examples/acme-company-os agent next --json >$verify_output_dir/palari-company-agent-next.json
run_smoke ./bin/palari docs check --json >$verify_output_dir/palari-company-docs-check.json
run_smoke ./bin/palari playbooks recommend WORK-0003 --json >$verify_output_dir/palari-company-playbooks.json
run_smoke ./bin/palari desktop-prototype --out "$verify_output_dir/desktop" --json >$verify_output_dir/palari-company-desktop.json
run_smoke ./bin/palari --workspace workspaces/palari-company-os validate --json >$verify_output_dir/palari-company-dogfood-validate.json
run_smoke ./bin/palari --workspace workspaces/palari-company-os queue --json >$verify_output_dir/palari-company-dogfood-queue.json
run_smoke ./bin/palari --workspace workspaces/palari-company-os detail WORK-REPO-0001 --json >$verify_output_dir/palari-company-dogfood-detail.json
run_smoke ./bin/palari --workspace workspaces/palari-company-os history --json >$verify_output_dir/palari-company-dogfood-history.json
run_smoke ./bin/palari --workspace workspaces/palari-company-os linear doctor --json >$verify_output_dir/palari-company-linear-doctor.json
run_smoke ./bin/palari --workspace tests/fixtures/workspaces/split-workspace validate --json >$verify_output_dir/palari-company-split-validate.json
run_smoke ./bin/palari --workspace tests/fixtures/workspaces/split-workspace detail WORK-SPLIT --json >$verify_output_dir/palari-company-split-detail.json
run_smoke ./bin/palari demo --no-pause >$verify_output_dir/palari-company-demo.txt
run_smoke ./scripts/pcaw_demo.sh >$verify_output_dir/pcaw-demo.txt

smoke_failed=0
for pid in "${smoke_pids[@]}"; do
  if ! wait "$pid"; then
    smoke_failed=1
  fi
done
if ((smoke_failed)); then
  printf 'One or more complete-gate CLI smokes failed.\n' >&2
  exit 1
fi

printf 'Palari Company OS verification passed.\n'
