#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# The local bin/palari wrapper exports the source tree for development. An
# isolated wheel smoke must not let that source checkout or its egg-info make
# pip believe the package is already installed inside the fresh venv.
unset PYTHONPATH PYTHONHOME
tmp_dir="$(mktemp -d)"
log_dir="$tmp_dir/logs"
mkdir "$log_dir"

cleanup() {
  status=$?
  if [[ "$status" -ne 0 ]]; then
    for log in "$log_dir"/*.log; do
      if [[ -f "$log" ]]; then
        printf 'install smoke log: %s\n' "$(basename "$log")" >&2
        tail -n 40 "$log" >&2
      fi
    done
  fi
  rm -rf "$tmp_dir"
  exit "$status"
}
trap cleanup EXIT

python3 -m venv "$tmp_dir/venv"
"$tmp_dir/venv/bin/python" -m pip wheel --disable-pip-version-check --no-deps \
  "$repo_dir" -w "$tmp_dir/wheelhouse" >"$log_dir/wheel.log"
wheel_path="$(find "$tmp_dir/wheelhouse" -name 'palari_company_os-*.whl' -print -quit)"
"$tmp_dir/venv/bin/python" -m pip install --disable-pip-version-check --no-index --no-deps \
  "$wheel_path" >"$log_dir/install.log"

"$tmp_dir/venv/bin/python" -c 'import palari_company_os; print(palari_company_os.__version__)' >"$log_dir/import.log"
"$tmp_dir/venv/bin/palari" --help >"$log_dir/help.log"
"$tmp_dir/venv/bin/palari" validate --json >"$log_dir/default-validate.json"
"$tmp_dir/venv/bin/palari" queue --json >"$log_dir/default-queue.json"
"$tmp_dir/venv/bin/palari" agent next --as PALARI-SOFIA --json >"$log_dir/agent-next.json"
"$tmp_dir/venv/bin/palari" agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json >"$log_dir/agent-brief.json"
"$tmp_dir/venv/bin/palari" agent check WORK-0003 --as PALARI-SOFIA --json >"$log_dir/agent-check.json"
"$tmp_dir/venv/bin/palari" agent finish WORK-0003 --as PALARI-SOFIA --json >"$log_dir/agent-finish.json"
"$tmp_dir/venv/bin/palari" integrations --json >"$log_dir/integrations.json"
"$tmp_dir/venv/bin/palari" integration check INT-SLACK-OPS --json >"$log_dir/integration-check.json"
"$tmp_dir/venv/bin/palari" integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify --json >"$log_dir/integration-plan.json"
mkdir "$tmp_dir/integration-workspace"
cp "$repo_dir/examples/acme-company-os/workspace.json" "$tmp_dir/integration-workspace/workspace.json"
"$tmp_dir/venv/bin/palari" --workspace "$tmp_dir/integration-workspace" integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify --record --id PLAN-INSTALL-SMOKE --json >"$log_dir/integration-plan-recorded.json"
"$tmp_dir/venv/bin/palari" --workspace "$tmp_dir/integration-workspace" integration approve PLAN-INSTALL-SMOKE --by HUMAN-FOUNDER --reason "install smoke" --json >"$log_dir/integration-plan-approved.json"
"$tmp_dir/venv/bin/palari" --workspace "$tmp_dir/integration-workspace" integration enqueue PLAN-INSTALL-SMOKE --by HUMAN-FOUNDER --json >"$log_dir/integration-plan-enqueued.json"
install_smoke_outbox_id="$("$tmp_dir/venv/bin/python" - "$log_dir/integration-plan-enqueued.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as handle:
    print(json.load(handle)["integration_outbox_item"]["id"])
PY
)"
"$tmp_dir/venv/bin/palari" --workspace "$tmp_dir/integration-workspace" integration outbox-cancel "$install_smoke_outbox_id" --by HUMAN-FOUNDER --reason "install smoke cancel" --json >"$log_dir/integration-outbox-canceled.json"
"$tmp_dir/venv/bin/palari" --workspace "$tmp_dir/integration-workspace" detail WORK-0001 --json >"$log_dir/integration-detail.json"
"$tmp_dir/venv/bin/palari" --workspace "$tmp_dir/integration-workspace" history --json >"$log_dir/integration-history.json"
"$tmp_dir/venv/bin/palari" --workspace "$repo_dir/examples/acme-company-os" validate --json >"$log_dir/explicit-validate.json"
cp -R "$repo_dir/spec/pcaw/v1/vectors/valid/accepted" "$tmp_dir/proof-bundle"
mkdir "$tmp_dir/offline-python"
printf '%s\n' \
  'import socket' \
  'def _offline(*args, **kwargs):' \
  '    raise RuntimeError("network disabled during PCAW install smoke")' \
  'socket.socket = _offline' >"$tmp_dir/offline-python/sitecustomize.py"
(
  cd "$tmp_dir"
  PYTHONPATH="$tmp_dir/offline-python" "$tmp_dir/venv/bin/palari" proof verify \
    proof-bundle/statement.json --subject-root proof-bundle --json \
    >"$log_dir/pcaw-offline-verify.json"
)

printf 'Palari Company OS wheel install smoke passed.\n'
