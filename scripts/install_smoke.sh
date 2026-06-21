#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

python3 -m venv "$tmp_dir/venv"
"$tmp_dir/venv/bin/python" -m pip install --disable-pip-version-check --upgrade pip >/tmp/palari-company-os-install-smoke-pip.log
"$tmp_dir/venv/bin/python" -m pip wheel --disable-pip-version-check --no-deps "$repo_dir" -w "$tmp_dir/wheelhouse" >/tmp/palari-company-os-install-smoke-wheel.log
wheel_path="$(find "$tmp_dir/wheelhouse" -name 'palari_company_os-*.whl' -print -quit)"
"$tmp_dir/venv/bin/python" -m pip install --disable-pip-version-check "$wheel_path" >/tmp/palari-company-os-install-smoke-install.log

"$tmp_dir/venv/bin/python" -c 'import palari_company_os; print(palari_company_os.__version__)' >/tmp/palari-company-os-install-smoke-import.log
"$tmp_dir/venv/bin/palari" --help >/tmp/palari-company-os-install-smoke-help.log
"$tmp_dir/venv/bin/palari" validate --json >/tmp/palari-company-os-install-smoke-default-validate.json
"$tmp_dir/venv/bin/palari" queue --json >/tmp/palari-company-os-install-smoke-default-queue.json
"$tmp_dir/venv/bin/palari" integrations --json >/tmp/palari-company-os-install-smoke-integrations.json
"$tmp_dir/venv/bin/palari" integration check INT-SLACK-OPS --json >/tmp/palari-company-os-install-smoke-integration-check.json
"$tmp_dir/venv/bin/palari" integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify --json >/tmp/palari-company-os-install-smoke-integration-plan.json
mkdir "$tmp_dir/integration-workspace"
cp "$repo_dir/examples/acme-company-os/workspace.json" "$tmp_dir/integration-workspace/workspace.json"
"$tmp_dir/venv/bin/palari" --workspace "$tmp_dir/integration-workspace" integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify --record --id PLAN-INSTALL-SMOKE --json >/tmp/palari-company-os-install-smoke-integration-plan-recorded.json
"$tmp_dir/venv/bin/palari" --workspace "$tmp_dir/integration-workspace" integration approve PLAN-INSTALL-SMOKE --by HUMAN-FOUNDER --reason "install smoke" --json >/tmp/palari-company-os-install-smoke-integration-plan-approved.json
"$tmp_dir/venv/bin/palari" --workspace "$tmp_dir/integration-workspace" integration enqueue PLAN-INSTALL-SMOKE --by HUMAN-FOUNDER --json >/tmp/palari-company-os-install-smoke-integration-plan-enqueued.json
install_smoke_outbox_id="$("$tmp_dir/venv/bin/python" - <<'PY'
import json
with open("/tmp/palari-company-os-install-smoke-integration-plan-enqueued.json", encoding="utf-8") as handle:
    print(json.load(handle)["integration_outbox_item"]["id"])
PY
)"
"$tmp_dir/venv/bin/palari" --workspace "$tmp_dir/integration-workspace" integration outbox-cancel "$install_smoke_outbox_id" --by HUMAN-FOUNDER --reason "install smoke cancel" --json >/tmp/palari-company-os-install-smoke-integration-outbox-canceled.json
"$tmp_dir/venv/bin/palari" --workspace "$tmp_dir/integration-workspace" detail WORK-0001 --json >/tmp/palari-company-os-install-smoke-integration-detail.json
"$tmp_dir/venv/bin/palari" --workspace "$tmp_dir/integration-workspace" history --json >/tmp/palari-company-os-install-smoke-integration-history.json
"$tmp_dir/venv/bin/palari" --workspace "$repo_dir/examples/acme-company-os" validate --json >/tmp/palari-company-os-install-smoke-explicit-validate.json
"$tmp_dir/venv/bin/palari" desktop-prototype --out "$tmp_dir/desktop" --json >/tmp/palari-company-os-install-smoke-desktop.json

test -f "$tmp_dir/desktop/index.html"
printf 'Palari Company OS wheel install smoke passed.\n'
