from __future__ import annotations

from copy import deepcopy
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
    objects: list[dict[str, str]] = [
        {"type": "proposal", "collection": "proposals", "id": proposal_id},
        {"type": "work", "collection": "work_items", "id": work_id},
    ]
    workbench_id = str(work.get("workbench_id") or "")
    if workbench_id:
        workbench = _find(_records(store.data, "workbenches"), workbench_id)
        if workbench is None:
            raise WorkspaceError(f"workbench not found: {workbench_id}")
        outputs = [str(item) for item in workbench.get("output_target_ids", [])]
        added = [path for path in work.get("output_targets", []) if path not in outputs]
        if added:
            workbench["output_target_ids"] = outputs + added
            objects.insert(
                0,
                {"type": "workbench", "collection": "workbenches", "id": workbench_id},
            )
    proposal.update(
        {
            "status": "adopted",
            "linked_work": work_id,
            "decided_by": human_id,
            "decided_at": utc_timestamp(),
        }
    )
    if reason:
        proposal["reason"] = reason
    workspace = write_store(
        store,
        metadata=MutationMetadata(
            command="approve idea",
            actor=human_id,
            action="approved",
            timestamp=utc_timestamp(),
            objects=tuple(objects),
            reason=reason,
        ),
    )
    return {
        "schema_version": "palari.work_idea_accept.v1",
        "action": "idea-approved",
        "idea_id": proposal_id,
        "work_item_id": work_id,
        "work_item": work,
        "workspace": workspace.name,
        "next_action": f"Run `palari agent start --next --as {work['palari']} --json`.",
    }


def _work_from_proposal(proposal: dict[str, Any], work_id: str) -> dict[str, Any]:
    fields = (
        "title", "goal", "palari", "workbench_id", "dependency_ids", "risk", "intensity",
        "scope", "allowed_resources", "allowed_sources", "allowed_actions", "output_targets",
        "path_intents", "forbidden_actions", "acceptance_target", "verification_expectations",
        "recommended_playbooks", "conflict_targets", "parallel_policy", "required_approval_count",
        "external_provider", "external_id", "external_key", "external_url", "external_updated_at",
    )
    work = {"id": work_id, "status": "active"}
    for field in fields:
        if field in proposal:
            work[field] = deepcopy(proposal[field])
    return work


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
