#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
integration_smoke_dir="$(mktemp -d)"
trap 'rm -rf "$integration_smoke_dir"' EXIT

bash -n scripts/install_smoke.sh scripts/verify.sh
python3 -S -m unittest discover -s tests
python3 -S scripts/check_style.py
python3 -S -m compileall -q src
python3 -S -m json.tool examples/acme-company-os/workspace.json >/tmp/palari-company-workspace-json-check.json
python3 -S -m json.tool workspaces/palari-company-os/workspace.json >/tmp/palari-company-dogfood-workspace-json-check.json
python3 -S -m json.tool schemas/workspace.schema.json >/tmp/palari-company-schema-json-check.json

./bin/palari validate --json >/tmp/palari-company-validate.json
./bin/palari --workspace workspaces/palari-company-os validate --json >/tmp/palari-company-dogfood-validate.json
./bin/palari --workspace tests/fixtures/workspaces/split-workspace validate --json >/tmp/palari-company-split-validate.json
./bin/palari state --json >/tmp/palari-company-state.json
./bin/palari --workspace workspaces/palari-company-os state --json >/tmp/palari-company-dogfood-state.json
./bin/palari queue --json >/tmp/palari-company-queue.json
./bin/palari --workspace workspaces/palari-company-os queue --json >/tmp/palari-company-dogfood-queue.json
./bin/palari detail WORK-0001 --json >/tmp/palari-company-detail-work-0001.json
./bin/palari --workspace workspaces/palari-company-os detail WORK-REPO-0001 --json >/tmp/palari-company-dogfood-detail-work-repo-0001.json
./bin/palari --workspace tests/fixtures/workspaces/split-workspace detail WORK-SPLIT --json >/tmp/palari-company-split-detail-work-split.json
./bin/palari agent next --as PALARI-SOFIA --json >/tmp/palari-company-agent-next-sofia.json
./bin/palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json >/tmp/palari-company-agent-brief-ready.json
agent_smoke_dir="$integration_smoke_dir/agent"
mkdir -p "$agent_smoke_dir"
cp examples/acme-company-os/workspace.json "$agent_smoke_dir/workspace.json"
./bin/palari --workspace "$agent_smoke_dir" agent start WORK-0003 --as PALARI-SOFIA --mode execute --json >/tmp/palari-company-agent-start-ready.json
./bin/palari --workspace "$agent_smoke_dir" agent check WORK-0003 --as PALARI-SOFIA --mode execute --changed docs/product/company-os.md --json >/tmp/palari-company-agent-check-changed.json
./bin/palari --workspace "$agent_smoke_dir" agent release WORK-0003 --as PALARI-SOFIA --json >/tmp/palari-company-agent-release.json
./bin/palari agent start WORK-0007 --as PALARI-SOFIA --mode execute --json >/tmp/palari-company-agent-start-blocked.json
./bin/palari agent check WORK-0003 --as PALARI-SOFIA --json >/tmp/palari-company-agent-check-work-0003.json
./bin/palari agent check WORK-0007 --as PALARI-SOFIA --json >/tmp/palari-company-agent-check-work-0007.json
./bin/palari agent finish WORK-0003 --as PALARI-SOFIA --json >/tmp/palari-company-agent-finish-work-0003.json
./bin/palari agent finish WORK-0007 --as PALARI-SOFIA --json >/tmp/palari-company-agent-finish-work-0007.json
./bin/palari playbooks sources --json >/tmp/palari-company-playbook-sources.json
./bin/palari playbooks recommend WORK-0003 --json >/tmp/palari-company-playbook-recommend.json
./bin/palari integrations --json >/tmp/palari-company-integrations.json
./bin/palari integration check INT-SLACK-OPS --json >/tmp/palari-company-integration-check.json
./bin/palari integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify --json >/tmp/palari-company-integration-plan.json
cp examples/acme-company-os/workspace.json "$integration_smoke_dir/workspace.json"
./bin/palari --workspace "$integration_smoke_dir" integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify --record --id PLAN-SMOKE --json >/tmp/palari-company-integration-plan-recorded.json
./bin/palari --workspace "$integration_smoke_dir" integration approve PLAN-SMOKE --by HUMAN-FOUNDER --reason "verification smoke" --json >/tmp/palari-company-integration-plan-approved.json
./bin/palari --workspace "$integration_smoke_dir" integration enqueue PLAN-SMOKE --by HUMAN-FOUNDER --json >/tmp/palari-company-integration-plan-enqueued.json
smoke_outbox_id="$(python3 - <<'PY'
import json
with open("/tmp/palari-company-integration-plan-enqueued.json", encoding="utf-8") as handle:
    print(json.load(handle)["integration_outbox_item"]["id"])
PY
)"
./bin/palari --workspace "$integration_smoke_dir" integration outbox-cancel "$smoke_outbox_id" --by HUMAN-FOUNDER --reason "verification smoke cancel" --json >/tmp/palari-company-integration-outbox-canceled.json
./bin/palari --workspace "$integration_smoke_dir" queue --json >/tmp/palari-company-integration-plan-queue.json
./bin/palari --workspace "$integration_smoke_dir" detail WORK-0001 --json >/tmp/palari-company-integration-plan-detail.json
./bin/palari --workspace "$integration_smoke_dir" history --json >/tmp/palari-company-integration-plan-history.json
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json --json >/tmp/palari-company-scope-allowed.json
./bin/palari scope WORK-0001 --changed secrets.env --action deploy --json >/tmp/palari-company-scope-blocked.json
./bin/palari history --json >/tmp/palari-company-history.json
./bin/palari --workspace workspaces/palari-company-os history --json >/tmp/palari-company-dogfood-history.json
./bin/palari maintainer status --json >/tmp/palari-company-maintainer-status.json
rm -rf /tmp/palari-company-dashboard-acme /tmp/palari-company-dashboard-dogfood /tmp/palari-company-desktop-prototype
./bin/palari --workspace examples/acme-company-os dashboard --out /tmp/palari-company-dashboard-acme --json >/tmp/palari-company-dashboard-acme.json
./bin/palari --workspace workspaces/palari-company-os dashboard --out /tmp/palari-company-dashboard-dogfood --json >/tmp/palari-company-dashboard-dogfood.json
./bin/palari desktop-prototype --out /tmp/palari-company-desktop-prototype --json >/tmp/palari-company-desktop-prototype.json
grep -q 'data-tab-panel="queue"' /tmp/palari-company-dashboard-acme/index.html
grep -q 'data-tab-panel="work"' /tmp/palari-company-dashboard-acme/index.html
grep -q 'data-tab-panel="trust"' /tmp/palari-company-dashboard-acme/index.html
grep -q 'data-tab-panel="history"' /tmp/palari-company-dashboard-acme/index.html
grep -q 'data-tab-panel="authority"' /tmp/palari-company-dashboard-acme/index.html
grep -q 'palari agent finish WORK-0007 --as PALARI-SOFIA' /tmp/palari-company-dashboard-acme/index.html
grep -q 'RECEIPT-0001' /tmp/palari-company-dashboard-acme/index.html
grep -q 'RECEIPT-REPO-0001' /tmp/palari-company-dashboard-dogfood/index.html
grep -q 'Palari Desktop Shell Prototype' /tmp/palari-company-desktop-prototype/index.html
grep -q 'External writes' /tmp/palari-company-desktop-prototype/index.html
grep -q 'data-mobile-target="chat"' /tmp/palari-company-desktop-prototype/index.html
grep -q '"schema_version": "palari.agent_next.v1"' /tmp/palari-company-agent-next-sofia.json
grep -q '"work_item_id": "WORK-0003"' /tmp/palari-company-agent-next-sofia.json
grep -q '"status": "ready"' /tmp/palari-company-agent-brief-ready.json
grep -q '"packet_id": "PACKET-WORK-0003-PALARI-SOFIA-EXECUTE-V1"' /tmp/palari-company-agent-brief-ready.json
grep -q '"status": "claimed"' /tmp/palari-company-agent-start-ready.json
grep -q '"packet_path": ".palari/packets/PACKET-WORK-0003-PALARI-SOFIA-EXECUTE-V1.json"' /tmp/palari-company-agent-start-ready.json
grep -q '"code": "FILE_CHANGES_WITHIN_WRITE_BOUNDARY"' /tmp/palari-company-agent-check-changed.json
grep -q '"status": "released"' /tmp/palari-company-agent-release.json
grep -q '"status": "blocked"' /tmp/palari-company-agent-start-blocked.json
grep -q 'DEPENDENCY_NOT_TERMINAL' /tmp/palari-company-agent-start-blocked.json
grep -q '"schema_version": "palari.agent_check.v1"' /tmp/palari-company-agent-check-work-0003.json
grep -q '"ok": false' /tmp/palari-company-agent-check-work-0003.json
grep -q 'RECEIPT_PRESENT' /tmp/palari-company-agent-check-work-0003.json
grep -q 'DEPENDENCY_NOT_TERMINAL' /tmp/palari-company-agent-check-work-0007.json
grep -q '"schema_version": "palari.agent_finish.v1"' /tmp/palari-company-agent-finish-work-0003.json
grep -q '"status": "missing-proof"' /tmp/palari-company-agent-finish-work-0003.json
grep -q '"status": "handoff-ready"' /tmp/palari-company-agent-finish-work-0007.json
grep -q 'superpowers:verification-before-completion' /tmp/palari-company-playbook-recommend.json
grep -q '"would_call_provider": false' /tmp/palari-company-integration-plan.json
grep -q '"recorded": true' /tmp/palari-company-integration-plan-recorded.json
grep -q '"status": "approved"' /tmp/palari-company-integration-plan-approved.json
grep -q '"would_call_provider": false' /tmp/palari-company-integration-plan-approved.json
grep -q '"status": "queued"' /tmp/palari-company-integration-plan-enqueued.json
grep -q '"would_call_provider": false' /tmp/palari-company-integration-plan-enqueued.json
grep -q '"status": "canceled"' /tmp/palari-company-integration-outbox-canceled.json
grep -q '"would_call_provider": false' /tmp/palari-company-integration-outbox-canceled.json
grep -q 'outbox-canceled' /tmp/palari-company-integration-plan-queue.json
grep -q 'PLAN-SMOKE' /tmp/palari-company-integration-plan-detail.json
grep -q 'PLAN-SMOKE' /tmp/palari-company-integration-plan-history.json
grep -q 'canceled' /tmp/palari-company-integration-plan-history.json
grep -q 'integration_outbox' /tmp/palari-company-integration-plan-detail.json

printf 'Palari Company OS verification passed.\n'
