from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .history import append_history_event
from .read_models import detail, queue_items
from .store import WorkspaceStore, load_store, validate_data, write_store
from .workspace import WorkspaceError, latest_for_work


COLLECTIONS = {
    "goal": "goals",
    "human": "humans",
    "palari": "palaris",
    "source": "sources",
    "playbook-source": "playbook_sources",
    "decision": "decisions",
    "work": "work_items",
    "attempt": "attempts",
    "evidence": "evidence_runs",
    "review": "review_verdicts",
    "human-decision": "human_decisions",
    "receipt": "receipts",
    "outcome": "outcomes",
}

INTEGER_FIELDS = {"required_approval_count"}
BOOLEAN_FIELDS = {"selected", "enabled"}
LIST_FIELDS = {
    "success_criteria",
    "linked_palaris",
    "linked_work",
    "linked_decisions",
    "aliases",
    "approval_capabilities",
    "skills",
    "ownership_areas",
    "allowed_inputs",
    "forbidden_inputs",
    "forbidden_actions",
    "standards",
    "memory_sources",
    "linked_goals",
    "active_work",
    "outcomes",
    "options",
    "tradeoffs",
    "allowed_resources",
    "allowed_sources",
    "allowed_actions",
    "output_targets",
    "verification_expectations",
    "recommended_playbooks",
    "included_playbooks",
    "commits",
    "changed_files",
    "commands",
    "artifacts",
    "findings",
    "checks_inspected",
    "residual_risks",
    "allowed_palaris",
    "sources_used",
    "actions_taken",
    "outputs_created",
    "external_writes",
    "not_done",
    "undo_refs",
    "useful",
    "failed",
    "follow_up_needed",
    "model_worker_notes",
}


@dataclass(frozen=True)
class MutationResult:
    action: str
    collection: str
    record_id: str
    workspace: str
    next_action: str = ""


def create_record(
    workspace_path: str,
    kind: str,
    record: dict[str, Any],
    *,
    command: str = "",
    actor: str = "",
) -> MutationResult:
    collection = _collection(kind)
    record_id = _record_id(record)
    store = load_store(workspace_path)
    records = _records(store, collection)
    if _find(records, record_id) is not None:
        raise WorkspaceError(f"{kind} already exists: {record_id}")
    records.append(record)
    workspace = write_store(store)
    append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command=command or f"{kind} create",
        action="created",
        object_type=kind,
        object_collection=collection,
        object_id=record_id,
        actor=_event_actor(record, actor),
        before=None,
        after=record,
    )
    return MutationResult("created", collection, record_id, workspace.name)


def update_record(
    workspace_path: str,
    kind: str,
    record_id: str,
    updates: dict[str, Any],
    *,
    command: str = "",
    actor: str = "",
) -> MutationResult:
    collection = _collection(kind)
    store = load_store(workspace_path)
    records = _records(store, collection)
    record = _find(records, record_id)
    if record is None:
        raise WorkspaceError(f"{kind} not found: {record_id}")
    before = deepcopy(record)
    record.update(updates)
    workspace = write_store(store)
    append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command=command or f"{kind} update",
        action="updated",
        object_type=kind,
        object_collection=collection,
        object_id=record_id,
        actor=_event_actor(record, actor),
        before=before,
        after=record,
    )
    return MutationResult("updated", collection, record_id, workspace.name)


def update_human_decision(
    workspace_path: str,
    record_id: str,
    updates: dict[str, Any],
    *,
    command: str = "",
    actor: str = "",
) -> MutationResult:
    store = load_store(workspace_path)
    records = _records(store, "human_decisions")
    record = _find(records, record_id)
    if record is None:
        raise WorkspaceError(f"human-decision not found: {record_id}")
    merged = dict(record)
    merged.update(updates)
    if merged.get("decision") in {"accepted", "approved"} or merged.get("status") in {
        "accepted",
        "approved",
    }:
        workspace = validate_data(store.data_path, store.data)
        _assert_acceptance_allowed(
            workspace,
            str(merged.get("work_item_id") or ""),
            str(merged.get("human_id") or ""),
            str(merged.get("reviewed_head") or ""),
        )
    before = deepcopy(record)
    record.update(updates)
    workspace = write_store(store)
    append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command=command or "human-decision update",
        action="updated",
        object_type="human-decision",
        object_collection="human_decisions",
        object_id=record_id,
        actor=_event_actor(record, actor),
        before=before,
        after=record,
    )
    return MutationResult("updated", "human_decisions", record_id, workspace.name)


def complete_work(
    workspace_path: str,
    work_id: str,
    status: str = "completed",
    *,
    command: str = "",
    actor: str = "",
) -> MutationResult:
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    work_detail = detail(workspace, work_id)
    if work_detail["safety"]["integration_state"] != "ready":
        raise WorkspaceError(
            f"work {work_id} cannot be completed: integration_state is "
            f"{work_detail['safety']['integration_state']}; next action is "
            f"{work_detail['next_action']}"
        )
    work = _find(_records(store, "work_items"), work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    before = deepcopy(work)
    work["status"] = status
    workspace = write_store(store)
    append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command=command or "work complete",
        action="completed",
        object_type="work",
        object_collection="work_items",
        object_id=work_id,
        actor=_event_actor(work, actor),
        before=before,
        after=work,
    )
    return MutationResult("completed", "work_items", work_id, workspace.name)


def create_human_decision(
    workspace_path: str,
    record: dict[str, Any],
    *,
    command: str = "",
    actor: str = "",
) -> MutationResult:
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    work_id = str(record.get("work_item_id") or "")
    human_id = str(record.get("human_id") or "")
    decision = str(record.get("decision") or "")
    reviewed_head = str(record.get("reviewed_head") or "")
    if decision in {"accepted", "approved"}:
        _assert_acceptance_allowed(workspace, work_id, human_id, reviewed_head)
    result = create_record(
        workspace_path,
        "human-decision",
        record,
        command=command or "human-decision record",
        actor=actor,
    )
    workspace = validate_data(load_store(workspace_path).data_path, load_store(workspace_path).data)
    item = next(item for item in queue_items(workspace) if item.id == work_id)
    return MutationResult(
        result.action,
        result.collection,
        result.record_id,
        result.workspace,
        next_action=item.next_action,
    )


def parse_setters(setters: list[str], list_setters: list[str]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for item in setters:
        key, value = _split_assignment(item)
        updates[key] = _coerce_value(key, value)
    for item in list_setters:
        key, value = _split_assignment(item)
        updates[key] = _coerce_list(value)
    return updates


def _assert_acceptance_allowed(
    workspace: Any,
    work_id: str,
    human_id: str,
    reviewed_head: str,
) -> None:
    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    human = workspace.human(human_id)
    if human is None:
        raise WorkspaceError(f"human not found: {human_id}")
    if work.required_approval_capability and (
        work.required_approval_capability not in human.approval_capabilities
    ):
        raise WorkspaceError(
            f"human {human_id} lacks required approval capability "
            f"{work.required_approval_capability}"
        )
    attempt = latest_for_work(workspace.attempts, work_id)
    evidence = latest_for_work(workspace.evidence_runs, work_id)
    review = latest_for_work(workspace.review_verdicts, work_id)
    if attempt is None:
        raise WorkspaceError(f"work {work_id} has no attempt; cannot accept")
    attempt_head = attempt.commits[-1] if attempt.commits else ""
    if evidence is None:
        raise WorkspaceError(f"work {work_id} has no evidence; cannot accept")
    if evidence.status != "passed":
        raise WorkspaceError(f"work {work_id} evidence is {evidence.status}; cannot accept")
    if evidence.head_sha != attempt_head:
        raise WorkspaceError(f"work {work_id} evidence is stale; cannot accept")
    if review is None:
        raise WorkspaceError(f"work {work_id} has no review; cannot accept")
    if review.verdict != "accept-ready":
        raise WorkspaceError(f"work {work_id} review is {review.verdict}; cannot accept")
    if review.reviewed_head != evidence.head_sha:
        raise WorkspaceError(f"work {work_id} review is stale; cannot accept")
    if reviewed_head != review.reviewed_head:
        raise WorkspaceError(
            f"human decision head {reviewed_head} does not match reviewed head {review.reviewed_head}"
        )


def _collection(kind: str) -> str:
    try:
        return COLLECTIONS[kind]
    except KeyError as exc:
        raise WorkspaceError(f"unknown object type: {kind}") from exc


def _records(store: WorkspaceStore, collection: str) -> list[dict[str, Any]]:
    records = store.data.setdefault(collection, [])
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise WorkspaceError(f"{collection} must be a list of objects")
    return records


def _record_id(record: dict[str, Any]) -> str:
    record_id = record.get("id")
    if not isinstance(record_id, str) or not record_id:
        raise WorkspaceError("record id is required")
    return record_id


def _find(records: list[dict[str, Any]], record_id: str) -> dict[str, Any] | None:
    for record in records:
        if record.get("id") == record_id:
            return record
    return None


def _split_assignment(item: str) -> tuple[str, str]:
    if "=" not in item:
        raise WorkspaceError(f"expected FIELD=VALUE assignment, got: {item}")
    key, value = item.split("=", 1)
    if not key:
        raise WorkspaceError(f"assignment has empty field name: {item}")
    return key, value


def _coerce_value(key: str, value: str) -> Any:
    if key in INTEGER_FIELDS:
        try:
            return int(value)
        except ValueError as exc:
            raise WorkspaceError(f"{key} must be an integer") from exc
    if key in BOOLEAN_FIELDS:
        lowered = value.lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
        raise WorkspaceError(f"{key} must be a boolean")
    if key in LIST_FIELDS:
        return _coerce_list(value)
    return value


def _coerce_list(value: str) -> list[str]:
    return [] if value == "" else [part.strip() for part in value.split(",")]


def _event_actor(record: dict[str, Any], actor: str) -> str:
    return actor or str(record.get("human_id") or record.get("actor") or "")
