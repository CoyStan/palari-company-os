from __future__ import annotations

import json
from pathlib import Path


PORTABLE_AGENT_WORK_IDS = {"WORK-0001", "WORK-0007"}


def write_portable_agent_workspace(source: Path, destination: Path) -> None:
    """Write the stable legacy slice used by agent and Git-hook tests.

    The dogfood workspace contains exact artifact bindings to its repository
    root. Copying those accepted records to a temporary directory must fail
    validation, so tests that need only legacy agent fixtures must not import
    the unrelated live lifecycle state.
    """

    raw = json.loads(source.read_text(encoding="utf-8"))
    raw["work_items"] = [
        item for item in raw.get("work_items", []) if item.get("id") in PORTABLE_AGENT_WORK_IDS
    ]
    for collection in ("attempts", "receipts"):
        raw[collection] = [
            item
            for item in raw.get(collection, [])
            if item.get("work_item_id") in PORTABLE_AGENT_WORK_IDS
        ]
    for collection in (
        "acceptance_records",
        "decisions",
        "evidence_runs",
        "human_decisions",
        "integration_outbox",
        "integration_plans",
        "outcomes",
        "proposals",
        "review_verdicts",
    ):
        raw[collection] = []
    for palari in raw.get("palaris", []):
        palari["active_work"] = [
            work_id
            for work_id in palari.get("active_work", [])
            if work_id in PORTABLE_AGENT_WORK_IDS
        ]
        palari["outcomes"] = []
    for goal in raw.get("goals", []):
        goal["linked_work"] = [
            work_id
            for work_id in goal.get("linked_work", [])
            if work_id in PORTABLE_AGENT_WORK_IDS
        ]
        goal["linked_decisions"] = []
    destination.write_text(
        json.dumps(raw, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
