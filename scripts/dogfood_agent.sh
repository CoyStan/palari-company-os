#!/usr/bin/env bash
# Bootstrap one claim-bound dogfood edit session for an agent.
# Usage: ./scripts/dogfood_agent.sh PALARI-ID [workspace-path]
set -euo pipefail

palari_id="${1:-}"
workspace="${2:-.}"
if [[ -z "${palari_id}" ]]; then
  echo "usage: $0 PALARI-ID [workspace-path]" >&2
  exit 2
fi

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${root}/src${PYTHONPATH:+:$PYTHONPATH}"
cli=(python3 -S -m palari_company_os --workspace "${workspace}")

next_json="$("${cli[@]}" agent next --as "${palari_id}" --json)"
NEXT_JSON="${next_json}" python3 -S - <<'PY'
import json, os
payload = json.loads(os.environ["NEXT_JSON"])
print(json.dumps({
    "status": payload.get("status"),
    "next_step_type": payload.get("next_step_type"),
    "candidates": [
        {
            "work_id": item.get("work_id") or item.get("id"),
            "title": item.get("title"),
            "status": item.get("status"),
        }
        for item in (payload.get("candidates") or payload.get("items") or [])[:5]
    ],
}, indent=2, sort_keys=True))
PY

start_json="$("${cli[@]}" agent start --next --as "${palari_id}" --mode execute --json)"
START_JSON="${start_json}" python3 -S - <<'PY'
import json, os, sys
payload = json.loads(os.environ["START_JSON"])
start = payload.get("start") or payload
status = str(start.get("status") or payload.get("status") or "")
packet = payload.get("packet") or start.get("packet") or {}
allowed = (
    ((packet.get("allowed_paths") or {}).get("write"))
    or packet.get("allowed_write_paths")
    or []
)
print(json.dumps({
    "status": status,
    "work_id": start.get("work_id") or packet.get("work_id") or payload.get("work_id"),
    "allowed_paths.write": allowed,
    "blockers": payload.get("blockers") or start.get("blockers") or [],
    "message": payload.get("message") or start.get("message") or "",
}, indent=2, sort_keys=True))
if status != "claimed":
    sys.exit(1)
PY

echo "Dogfood session ready. Edit only allowed_paths.write, then:"
echo "  palari --workspace ${workspace} agent advance WORK-ID --as ${palari_id} --json"
