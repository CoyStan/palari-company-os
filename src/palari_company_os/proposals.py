from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .governance_journal import MutationMetadata, utc_timestamp
from .store import load_store, validate_data, write_store
from .transition_checks import assert_transition_allowed
from .workspace import WorkspaceError


def adopt_proposal(
    workspace_path: str,
    proposal_id: str,
    work_id: str,
    human_id: str,
    *,
    reason: str = "",
) -> dict[str, Any]:
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    if workspace.human(human_id) is None:
        raise WorkspaceError(f"human not found: {human_id}")
    proposals = _records(store.data, "proposals")
    proposal = _find(proposals, proposal_id)
    if proposal is None:
        raise WorkspaceError(f"proposal not found: {proposal_id}")
    if proposal.get("status") == "adopted":
        raise WorkspaceError(f"proposal already adopted: {proposal_id}")
    if proposal.get("status") in {"rejected", "deferred"}:
        raise WorkspaceError(f"proposal {proposal_id} is {proposal.get('status')}")
    if _find(_records(store.data, "work_items"), work_id) is not None:
        raise WorkspaceError(f"work already exists: {work_id}")
    assert_transition_allowed(
        workspace,
        "proposal_adopt",
        proposal_id,
        actor=human_id,
        context={"work_id": work_id},
    )

    work = _work_from_proposal(proposal, work_id)
    _records(store.data, "work_items").append(work)
    proposal.update(
        {
            "status": "adopted",
            "linked_work": work_id,
            "decided_by": human_id,
            "decided_at": _timestamp(),
        }
    )
    if reason:
        proposal["reason"] = reason
    workspace = write_store(
        store,
        metadata=MutationMetadata(
            command="proposal adopt",
            actor=human_id,
            action="adopted",
            timestamp=utc_timestamp(),
            objects=(
                {"type": "proposal", "collection": "proposals", "id": proposal_id},
                {"type": "work", "collection": "work_items", "id": work_id},
            ),
            reason=reason,
        ),
    )
    return {
        "action": "adopted",
        "proposal_id": proposal_id,
        "work_item_id": work_id,
        "workspace": workspace.name,
        "next_action": f"Run `palari detail {work_id}` and start a bounded attempt when ready.",
    }


def decide_proposal(
    workspace_path: str,
    proposal_id: str,
    human_id: str,
    status: str,
    *,
    reason: str,
) -> dict[str, Any]:
    if status not in {"rejected", "deferred"}:
        raise WorkspaceError(f"unsupported proposal decision: {status}")
    if not reason:
        raise WorkspaceError("proposal decision reason is required")
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    if workspace.human(human_id) is None:
        raise WorkspaceError(f"human not found: {human_id}")
    proposals = _records(store.data, "proposals")
    proposal = _find(proposals, proposal_id)
    if proposal is None:
        raise WorkspaceError(f"proposal not found: {proposal_id}")
    if proposal.get("status") == "adopted":
        raise WorkspaceError(f"proposal already adopted: {proposal_id}")
    proposal.update(
        {
            "status": status,
            "decided_by": human_id,
            "decided_at": _timestamp(),
            "reason": reason,
        }
    )
    workspace = write_store(
        store,
        metadata=MutationMetadata(
            command=f"proposal {status}",
            actor=human_id,
            action=status,
            timestamp=utc_timestamp(),
            objects=(
                {"type": "proposal", "collection": "proposals", "id": proposal_id},
            ),
            reason=reason,
        ),
    )
    return {
        "action": status,
        "proposal_id": proposal_id,
        "workspace": workspace.name,
        "next_action": "Review the queue for the next proposal or active work item.",
    }


def request_scope_expansion(
    workspace_path: str,
    work_id: str,
    decision_id: str,
    actor: str,
    *,
    read_paths: list[str],
    write_paths: list[str],
    actions: list[str],
    reason: str,
) -> dict[str, Any]:
    if not reason:
        raise WorkspaceError("scope expansion reason is required")
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    if _find(_records(store.data, "decisions"), decision_id) is not None:
        raise WorkspaceError(f"decision already exists: {decision_id}")
    decision = {
        "id": decision_id,
        "question": f"Should scope expand for {work_id}?",
        "status": "open",
        "context": _scope_context(read_paths, write_paths, actions, reason),
        "options": ["approve scope expansion", "reject scope expansion", "split into new work"],
        "tradeoffs": [
            "Approving changes the declared work boundary.",
            "Rejecting keeps the current attempt inside its packet.",
            "Splitting preserves parallel safety for unrelated changes.",
        ],
        "recommendation": "Do not expand scope until a human reviews the new boundary.",
        "safe_default": "reject scope expansion",
        "linked_goal": work.goal,
        "linked_work": work.id,
        "linked_palari": work.palari,
    }
    _records(store.data, "decisions").append(decision)
    workspace = write_store(
        store,
        metadata=MutationMetadata(
            command="work expand-scope",
            actor=actor or "local-operator",
            action="created",
            timestamp=utc_timestamp(),
            objects=(
                {"type": "decision", "collection": "decisions", "id": decision_id},
            ),
            reason=reason,
        ),
    )
    return {
        "action": "scope-expansion-requested",
        "decision_id": decision_id,
        "work_item_id": work_id,
        "workspace": workspace.name,
        "next_action": f"Resolve decision {decision_id} before expanding the packet boundary.",
    }


def _work_from_proposal(proposal: dict[str, Any], work_id: str) -> dict[str, Any]:
    fields = [
        "title",
        "goal",
        "palari",
        "risk",
        "intensity",
        "scope",
        "allowed_resources",
        "allowed_sources",
        "allowed_actions",
        "output_targets",
        "forbidden_actions",
        "acceptance_target",
        "verification_expectations",
        "recommended_playbooks",
        "conflict_targets",
        "parallel_policy",
        "external_provider",
        "external_id",
        "external_key",
        "external_url",
        "external_updated_at",
    ]
    work = {"id": work_id, "status": "proposed"}
    for field in fields:
        if field in proposal:
            work[field] = deepcopy(proposal[field])
    return work


def _scope_context(
    read_paths: list[str],
    write_paths: list[str],
    actions: list[str],
    reason: str,
) -> str:
    parts = [f"Reason: {reason}"]
    if read_paths:
        parts.append(f"Requested read paths: {', '.join(read_paths)}")
    if write_paths:
        parts.append(f"Requested write paths: {', '.join(write_paths)}")
    if actions:
        parts.append(f"Requested actions: {', '.join(actions)}")
    return "\n".join(parts)


def _records(data: dict[str, Any], collection: str) -> list[dict[str, Any]]:
    records = data.setdefault(collection, [])
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise WorkspaceError(f"{collection} must be a list of objects")
    return records


def _find(records: list[dict[str, Any]], record_id: str) -> dict[str, Any] | None:
    for record in records:
        if record.get("id") == record_id:
            return record
    return None


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
