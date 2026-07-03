#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
integration_smoke_dir="$(mktemp -d)"
verify_output_dir="$(mktemp -d)"
trap 'rm -rf "$integration_smoke_dir" "$verify_output_dir"' EXIT

bash -n scripts/install_smoke.sh scripts/verify.sh
python3 -S -m unittest discover -s tests
python3 -S scripts/check_style.py
python3 -S -m compileall -q src
python3 -S -m json.tool examples/acme-company-os/workspace.json >$verify_output_dir/palari-company-workspace-json-check.json
python3 -S -m json.tool workspaces/palari-company-os/workspace.json >$verify_output_dir/palari-company-dogfood-workspace-json-check.json
python3 -S -m json.tool schemas/workspace.schema.json >$verify_output_dir/palari-company-schema-json-check.json

./bin/palari validate --json >$verify_output_dir/palari-company-validate.json
./bin/palari --workspace workspaces/palari-company-os validate --json >$verify_output_dir/palari-company-dogfood-validate.json
./bin/palari --workspace tests/fixtures/workspaces/split-workspace validate --json >$verify_output_dir/palari-company-split-validate.json
./bin/palari state --json >$verify_output_dir/palari-company-state.json
./bin/palari --workspace workspaces/palari-company-os state --json >$verify_output_dir/palari-company-dogfood-state.json
./bin/palari queue --json >$verify_output_dir/palari-company-queue.json
./bin/palari --workspace workspaces/palari-company-os queue --json >$verify_output_dir/palari-company-dogfood-queue.json
./bin/palari detail WORK-0001 --json >$verify_output_dir/palari-company-detail-work-0001.json
./bin/palari --workspace workspaces/palari-company-os detail WORK-REPO-0001 --json >$verify_output_dir/palari-company-dogfood-detail-work-repo-0001.json
./bin/palari --workspace tests/fixtures/workspaces/split-workspace detail WORK-SPLIT --json >$verify_output_dir/palari-company-split-detail-work-split.json
./bin/palari agent next --as PALARI-SOFIA --json >$verify_output_dir/palari-company-agent-next-sofia.json
./bin/palari agent brief WORK-0003 --as PALARI-SOFIA --mode execute --json >$verify_output_dir/palari-company-agent-brief-ready.json
agent_smoke_dir="$integration_smoke_dir/agent"
mkdir -p "$agent_smoke_dir"
cp examples/acme-company-os/workspace.json "$agent_smoke_dir/workspace.json"
./bin/palari --workspace "$agent_smoke_dir" agent start WORK-0003 --as PALARI-SOFIA --mode execute --json >$verify_output_dir/palari-company-agent-start-ready.json
./bin/palari --workspace "$agent_smoke_dir" agent check WORK-0003 --as PALARI-SOFIA --mode execute --changed docs/product/company-os.md --json >$verify_output_dir/palari-company-agent-check-changed.json
./bin/palari --workspace "$agent_smoke_dir" agent release WORK-0003 --as PALARI-SOFIA --json >$verify_output_dir/palari-company-agent-release.json
./bin/palari agent start WORK-0007 --as PALARI-SOFIA --mode execute --json >$verify_output_dir/palari-company-agent-start-blocked.json
./bin/palari agent check WORK-0003 --as PALARI-SOFIA --json >$verify_output_dir/palari-company-agent-check-work-0003.json
./bin/palari agent check WORK-0007 --as PALARI-SOFIA --json >$verify_output_dir/palari-company-agent-check-work-0007.json
./bin/palari agent finish WORK-0003 --as PALARI-SOFIA --json >$verify_output_dir/palari-company-agent-finish-work-0003.json
./bin/palari agent finish WORK-0007 --as PALARI-SOFIA --json >$verify_output_dir/palari-company-agent-finish-work-0007.json
./bin/palari --workspace examples/acme-company-os mcp serve --repo . >$verify_output_dir/palari-company-mcp.jsonl <<'EOF'
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}
{"jsonrpc":"2.0","method":"notifications/initialized"}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"palari_agent_brief","arguments":{"work_id":"WORK-0003","palari_id":"PALARI-SOFIA","mode":"execute"}}}
EOF
./bin/palari playbooks sources --json >$verify_output_dir/palari-company-playbook-sources.json
./bin/palari playbooks recommend WORK-0003 --json >$verify_output_dir/palari-company-playbook-recommend.json
./bin/palari integrations --json >$verify_output_dir/palari-company-integrations.json
./bin/palari integration check INT-SLACK-OPS --json >$verify_output_dir/palari-company-integration-check.json
./bin/palari integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify --json >$verify_output_dir/palari-company-integration-plan.json
cp examples/acme-company-os/workspace.json "$integration_smoke_dir/workspace.json"
./bin/palari --workspace "$integration_smoke_dir" integration plan INT-SLACK-OPS --work WORK-0001 --event approval_requested --action notify --record --id PLAN-SMOKE --json >$verify_output_dir/palari-company-integration-plan-recorded.json
./bin/palari --workspace "$integration_smoke_dir" integration approve PLAN-SMOKE --by HUMAN-FOUNDER --reason "verification smoke" --json >$verify_output_dir/palari-company-integration-plan-approved.json
./bin/palari --workspace "$integration_smoke_dir" integration enqueue PLAN-SMOKE --by HUMAN-FOUNDER --json >$verify_output_dir/palari-company-integration-plan-enqueued.json
smoke_outbox_id="$(PALARI_SMOKE_ENQUEUE_JSON="$verify_output_dir/palari-company-integration-plan-enqueued.json" python3 - <<'PY'
import json
import os

with open(os.environ["PALARI_SMOKE_ENQUEUE_JSON"], encoding="utf-8") as handle:
    print(json.load(handle)["integration_outbox_item"]["id"])
PY
)"
./bin/palari --workspace "$integration_smoke_dir" integration outbox-cancel "$smoke_outbox_id" --by HUMAN-FOUNDER --reason "verification smoke cancel" --json >$verify_output_dir/palari-company-integration-outbox-canceled.json
./bin/palari --workspace "$integration_smoke_dir" queue --json >$verify_output_dir/palari-company-integration-plan-queue.json
./bin/palari --workspace "$integration_smoke_dir" detail WORK-0001 --json >$verify_output_dir/palari-company-integration-plan-detail.json
./bin/palari --workspace "$integration_smoke_dir" history --json >$verify_output_dir/palari-company-integration-plan-history.json
./bin/palari scope WORK-0001 --changed examples/acme-company-os/workspace.json --json >$verify_output_dir/palari-company-scope-allowed.json
./bin/palari scope WORK-0001 --changed secrets.env --action deploy --json >$verify_output_dir/palari-company-scope-blocked.json
./bin/palari history --json >$verify_output_dir/palari-company-history.json
./bin/palari --workspace workspaces/palari-company-os history --json >$verify_output_dir/palari-company-dogfood-history.json
./bin/palari maintainer status --json >$verify_output_dir/palari-company-maintainer-status.json
rm -rf $verify_output_dir/palari-company-dashboard-acme $verify_output_dir/palari-company-dashboard-dogfood $verify_output_dir/palari-company-desktop-prototype
./bin/palari --workspace examples/acme-company-os dashboard --out $verify_output_dir/palari-company-dashboard-acme --json >$verify_output_dir/palari-company-dashboard-acme.json
./bin/palari --workspace workspaces/palari-company-os dashboard --out $verify_output_dir/palari-company-dashboard-dogfood --json >$verify_output_dir/palari-company-dashboard-dogfood.json
./bin/palari desktop-prototype --out $verify_output_dir/palari-company-desktop-prototype --json >$verify_output_dir/palari-company-desktop-prototype.json
grep -q 'data-tab-panel="queue"' $verify_output_dir/palari-company-dashboard-acme/index.html
grep -q 'data-tab-panel="work"' $verify_output_dir/palari-company-dashboard-acme/index.html
grep -q 'data-tab-panel="trust"' $verify_output_dir/palari-company-dashboard-acme/index.html
grep -q 'data-tab-panel="history"' $verify_output_dir/palari-company-dashboard-acme/index.html
grep -q 'data-tab-panel="authority"' $verify_output_dir/palari-company-dashboard-acme/index.html
grep -q 'palari agent finish WORK-0007 --as PALARI-SOFIA' $verify_output_dir/palari-company-dashboard-acme/index.html
grep -q 'RECEIPT-0001' $verify_output_dir/palari-company-dashboard-acme/index.html
grep -q 'RECEIPT-REPO-0001' $verify_output_dir/palari-company-dashboard-dogfood/index.html
grep -q 'Palari Desktop Shell Prototype' $verify_output_dir/palari-company-desktop-prototype/index.html
grep -q 'External writes' $verify_output_dir/palari-company-desktop-prototype/index.html
grep -q 'data-mobile-target="chat"' $verify_output_dir/palari-company-desktop-prototype/index.html
grep -q '"schema_version": "palari.agent_next.v1"' $verify_output_dir/palari-company-agent-next-sofia.json
grep -q '"work_item_id": "WORK-0003"' $verify_output_dir/palari-company-agent-next-sofia.json
grep -q '"status": "ready"' $verify_output_dir/palari-company-agent-brief-ready.json
grep -q '"packet_id": "PACKET-WORK-0003-PALARI-SOFIA-EXECUTE-V1"' $verify_output_dir/palari-company-agent-brief-ready.json
grep -q '"status": "claimed"' $verify_output_dir/palari-company-agent-start-ready.json
grep -q '"packet_path": ".palari/packets/PACKET-WORK-0003-PALARI-SOFIA-EXECUTE-V1.json"' $verify_output_dir/palari-company-agent-start-ready.json
grep -q '"code": "FILE_CHANGES_WITHIN_WRITE_BOUNDARY"' $verify_output_dir/palari-company-agent-check-changed.json
grep -q '"status": "released"' $verify_output_dir/palari-company-agent-release.json
grep -q '"status": "blocked"' $verify_output_dir/palari-company-agent-start-blocked.json
grep -q 'DEPENDENCY_NOT_TERMINAL' $verify_output_dir/palari-company-agent-start-blocked.json
grep -q '"schema_version": "palari.agent_check.v1"' $verify_output_dir/palari-company-agent-check-work-0003.json
grep -q '"ok": false' $verify_output_dir/palari-company-agent-check-work-0003.json
grep -q 'RECEIPT_PRESENT' $verify_output_dir/palari-company-agent-check-work-0003.json
grep -q 'DEPENDENCY_NOT_TERMINAL' $verify_output_dir/palari-company-agent-check-work-0007.json
grep -q '"schema_version": "palari.agent_finish.v1"' $verify_output_dir/palari-company-agent-finish-work-0003.json
grep -q '"status": "missing-proof"' $verify_output_dir/palari-company-agent-finish-work-0003.json
grep -q '"status": "handoff-ready"' $verify_output_dir/palari-company-agent-finish-work-0007.json
grep -q '"serverInfo"' $verify_output_dir/palari-company-mcp.jsonl
grep -q '"palari_agent_brief"' $verify_output_dir/palari-company-mcp.jsonl
grep -q '"structuredContent"' $verify_output_dir/palari-company-mcp.jsonl
grep -q 'superpowers:verification-before-completion' $verify_output_dir/palari-company-playbook-recommend.json
grep -q '"would_call_provider": false' $verify_output_dir/palari-company-integration-plan.json
grep -q '"recorded": true' $verify_output_dir/palari-company-integration-plan-recorded.json
grep -q '"status": "approved"' $verify_output_dir/palari-company-integration-plan-approved.json
grep -q '"would_call_provider": false' $verify_output_dir/palari-company-integration-plan-approved.json
grep -q '"status": "queued"' $verify_output_dir/palari-company-integration-plan-enqueued.json
grep -q '"would_call_provider": false' $verify_output_dir/palari-company-integration-plan-enqueued.json
grep -q '"status": "canceled"' $verify_output_dir/palari-company-integration-outbox-canceled.json
grep -q '"would_call_provider": false' $verify_output_dir/palari-company-integration-outbox-canceled.json
grep -q 'outbox-canceled' $verify_output_dir/palari-company-integration-plan-queue.json
grep -q 'PLAN-SMOKE' $verify_output_dir/palari-company-integration-plan-detail.json
grep -q 'PLAN-SMOKE' $verify_output_dir/palari-company-integration-plan-history.json
grep -q 'canceled' $verify_output_dir/palari-company-integration-plan-history.json
grep -q 'integration_outbox' $verify_output_dir/palari-company-integration-plan-detail.json

printf 'Palari Company OS verification passed.\n'
