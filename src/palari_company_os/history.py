from __future__ import annotations

import getpass
import json
import os
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .store import workspace_file_path


def history_file_path(workspace_path: Path | str) -> Path:
    data_path = workspace_file_path(workspace_path)
    return data_path.parent / ".palari" / "history.jsonl"


def append_history_event(
    workspace_path: Path | str,
    *,
    schema_version: int,
    command: str,
    action: str,
    object_type: str,
    object_collection: str,
    object_id: str,
    actor: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data_path = workspace_file_path(workspace_path)
    event = {
        "event_id": f"event-{uuid.uuid4()}",
        "timestamp": _timestamp(),
        "actor": _actor(actor),
        "command": command,
        "action": action,
        "object_type": object_type,
        "object_collection": object_collection,
        "object_id": object_id,
        "workspace_file": _workspace_relative_path(data_path, data_path),
        "schema_version": schema_version,
        "before": _record_summary(before),
        "after": _record_summary(after),
        "changed_fields": _changed_fields(before, after),
    }
    history_path = history_file_path(data_path)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def read_history(workspace_path: Path | str, limit: int | None = None) -> dict[str, Any]:
    data_path = workspace_file_path(workspace_path)
    history_path = history_file_path(data_path)
    events: list[dict[str, Any]] = []
    if history_path.exists():
        for line in history_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    if limit is not None and limit >= 0:
        events = events[-limit:]
    return {
        "workspace_file": _workspace_relative_path(data_path, data_path),
        "history_file": _workspace_relative_path(data_path, history_path),
        "events": events,
    }


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _actor(actor: str) -> str:
    if actor:
        return actor
    env_actor = os.environ.get("PALARI_HISTORY_ACTOR")
    if env_actor:
        return env_actor
    return os.environ.get("USER") or getpass.getuser() or "local-user"


def _workspace_relative_path(data_path: Path, target_path: Path) -> str:
    try:
        return target_path.relative_to(data_path.parent).as_posix()
    except ValueError:
        return target_path.name


def _record_summary(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    summary: dict[str, Any] = {}
    for key in (
        "id",
        "title",
        "name",
        "status",
        "decision",
        "verdict",
        "work_item_id",
        "integration_id",
        "plan_id",
        "event",
        "action",
        "human_id",
        "actor",
        "enqueued_by",
        "reviewed_by",
        "reviewed_at",
        "decision_reason",
        "summary",
    ):
        if key in record:
            summary[key] = deepcopy(record[key])
    if not summary:
        summary = deepcopy(record)
    return summary


def _changed_fields(
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    before = before or {}
    after = after or {}
    changed: dict[str, dict[str, Any]] = {}
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value != after_value:
            changed[key] = {
                "before": deepcopy(before_value),
                "after": deepcopy(after_value),
            }
    return changed
