from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

from .history import append_history_event
from .read_models import detail, queue_items
from .record_order import record_time_key
from .store import WorkspaceStore, load_store, validate_data, write_store
from .transition_checks import assert_transition_allowed
from .workspace import WorkspaceError, current_attempt_for_work, latest_for_work


COLLECTIONS = {
    "goal": "goals",
    "human": "humans",
    "palari": "palaris",
    "source": "sources",
    "workbench": "workbenches",
    "playbook-source": "playbook_sources",
    "capability": "capabilities",
    "authority-profile": "authority_profiles",
    "decision": "decisions",
    "proposal": "proposals",
    "work": "work_items",
    "attempt": "attempts",
    "evidence": "evidence_runs",
    "review": "review_verdicts",
    "human-decision": "human_decisions",
    "acceptance": "acceptance_records",
    "receipt": "receipts",
    "outcome": "outcomes",
}

INTEGER_FIELDS = {"required_approval_count", "minimum_approval_count", "r5_approval_count"}
BOOLEAN_FIELDS = {
    "selected",
    "enabled",
    "redaction_required",
    "allow_agent_scope_expansion",
}
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
    "allowed_paths",
    "forbidden_paths",
    "allowed_palaris",
    "source_ids",
    "require_human_for_risks",
    "receipt_ready_risks",
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
    "goal_ids",
    "palari_ids",
    "human_ids",
    "source_ids",
    "output_target_ids",
    "dependency_ids",
    "conflict_targets",
    "sources_used",
    "actions_taken",
    "outputs_created",
    "planned_external_writes",
    "queued_external_writes",
    "external_writes",
    "not_done",
    "undo_refs",
    "useful",
    "failed",
    "follow_up_needed",
    "model_worker_notes",
}
TRANSITION_UPDATE_FIELDS = {
    "evidence": {
        "work_item_id",
        "attempt_id",
        "head_sha",
        "status",
        "commands",
        "artifacts",
        "artifact_hashes",
        "manifest_hash",
        "receipt_hash",
        "previous_receipt_hash",
    },
    "review": {
        "work_item_id",
        "reviewed_head",
        "reviewer",
        "verdict",
    },
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
    _assert_record_transition_allowed(store, kind, record)
    record = _prepare_record_for_create(store, kind, record)
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
    _reject_active_claim_work_update(store.data_path, kind, record_id, updates)
    _reject_generic_trust_transition(kind, record_id, record, updates)
    before = deepcopy(record)
    merged = dict(record)
    merged.update(updates)
    if _record_update_needs_transition(kind, updates):
        _assert_record_transition_allowed(store, kind, merged, allow_existing=True)
    record.update(updates)
    _prepare_record_for_update(store, kind, record, updates)
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


def _reject_active_claim_work_update(
    workspace_path: Any,
    kind: str,
    record_id: str,
    updates: dict[str, Any],
) -> None:
    """Keep generic authoring from changing a claimed work packet in place."""

    if kind != "work" or not updates:
        return
    authority_updates = set(updates) - {"current_attempt"}
    if not authority_updates:
        return
    from .agent_runtime import claim_is_active, read_claim

    claim = read_claim(workspace_path, record_id)
    if claim and claim_is_active(claim):
        raise WorkspaceError(
            f"work {record_id} has an active {claim.get('mode', 'unknown')} claim; "
            "generic work update cannot change its packet authority in place "
            f"({', '.join(sorted(authority_updates))}). "
            "Release the claim and route scope changes through an authorized handoff."
        )


def update_human_decision(
    workspace_path: str,
    record_id: str,
    updates: dict[str, Any],
    *,
    command: str = "",
    actor: str = "",
) -> MutationResult:
    updates = dict(updates)
    if set(updates) & {"decision", "status"} and "timestamp" not in updates:
        updates["timestamp"] = _timestamp()
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
        assert_transition_allowed(
            workspace,
            "human_decision_accept",
            str(merged.get("id") or record_id),
            actor=str(merged.get("human_id") or ""),
            context={
                "work_item_id": str(merged.get("work_item_id") or ""),
                "reviewed_head": str(merged.get("reviewed_head") or ""),
            },
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
    assert_work_completion_ready(workspace, work_id, actor=actor)
    work = _find(_records(store, "work_items"), work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    before = deepcopy(work)
    work["status"] = status
    _ensure_acceptance_record_for_completion(store, workspace, work_id, actor)
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


def assert_work_completion_ready(
    workspace: Any,
    work_id: str,
    *,
    actor: str = "",
) -> dict[str, Any]:
    """Apply the authoritative completion checks without mutating workspace state."""

    work_detail = detail(workspace, work_id)
    blocker = _completion_blocker(work_detail)
    if blocker:
        raise WorkspaceError(
            f"work {work_id} cannot be completed: {blocker}; "
            f"next action is {work_detail['next_action']}"
        )
    integrity_blocker = _completion_integrity_blocker(workspace, work_id)
    if integrity_blocker:
        raise WorkspaceError(f"work {work_id} cannot be completed: {integrity_blocker}")
    assert_transition_allowed(
        workspace,
        "work_complete",
        work_id,
        actor=actor,
    )
    return work_detail


def _completion_blocker(work_detail: dict[str, Any]) -> str:
    if work_detail["attention"] == "blocked":
        return work_detail["why"]
    integration_state = work_detail["safety"]["integration_state"]
    if integration_state == "ready":
        return ""
    if integration_state != "receipt-ready":
        return f"integration_state is {integration_state}"
    return _receipt_ready_completion_blocker(work_detail)


def _receipt_ready_completion_blocker(work_detail: dict[str, Any]) -> str:
    work = work_detail["work_item"]
    if work["risk"] not in {"R1", "R2"}:
        return f"receipt-ready completion requires R1/R2 risk, found {work['risk']}"
    if work.get("required_approval_count", 0) != 0:
        return "receipt-ready completion requires required_approval_count 0"
    unfinished_dependencies = [
        dependency["id"]
        for dependency in work_detail.get("dependencies", [])
        if dependency.get("status") not in {"completed", "closed", "done"}
    ]
    if unfinished_dependencies:
        return f"dependencies are unfinished: {', '.join(unfinished_dependencies)}"
    open_decisions = [
        decision["id"]
        for decision in work_detail.get("linked_decisions", [])
        if decision.get("status") not in {"decided", "answered", "closed"}
    ]
    if open_decisions:
        return f"linked decisions are open: {', '.join(open_decisions)}"
    receipt = work_detail.get("receipt") or {}
    if not receipt:
        return "receipt-ready completion requires a receipt"
    if (
        receipt.get("external_writes")
        or receipt.get("planned_external_writes")
        or receipt.get("queued_external_writes")
    ):
        return "receipt-ready completion requires no external writes"
    return ""


def _completion_integrity_blocker(workspace: Any, work_id: str) -> str:
    work = workspace.work_item(work_id)
    if work is not None and not (
        work.risk in {"R1", "R2"} and work.required_approval_count == 0
    ):
        review = latest_for_work(workspace.review_verdicts, work_id)
        if review is None:
            return "exact review binding is missing"
        from .governance_binding import current_review_binding_errors

        binding_errors = current_review_binding_errors(
            workspace, review, require_output_coverage=True
        )
        if binding_errors:
            return binding_errors[0]
    evidence = latest_for_work(workspace.evidence_runs, work_id)
    if evidence is None or not evidence.manifest_hash:
        return ""
    from .evidence_manifest import verify_evidence

    verification = verify_evidence(workspace, evidence.id, require_output_coverage=True)
    if verification["ok"]:
        return ""
    return "evidence manifest verification failed"


def create_human_decision(
    workspace_path: str,
    record: dict[str, Any],
    *,
    command: str = "",
    actor: str = "",
) -> MutationResult:
    record = dict(record)
    if not record.get("timestamp"):
        record["timestamp"] = _timestamp()
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    work_id = str(record.get("work_item_id") or "")
    human_id = str(record.get("human_id") or "")
    decision = str(record.get("decision") or "")
    reviewed_head = str(record.get("reviewed_head") or "")
    if decision in {"accepted", "approved"}:
        _assert_acceptance_allowed(workspace, work_id, human_id, reviewed_head)
        assert_transition_allowed(
            workspace,
            "human_decision_accept",
            str(record.get("id") or ""),
            actor=human_id,
            context={
                "work_item_id": work_id,
                "reviewed_head": reviewed_head,
            },
        )
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


def accept_work(
    workspace_path: str,
    work_id: str,
    human_id: str,
    reviewed_head: str,
    *,
    decision_id: str = "",
    acceptance_id: str = "",
    reason: str = "",
    authority_profile: str = "team-safe",
    command: str = "",
) -> MutationResult:
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    _assert_acceptance_allowed(workspace, work_id, human_id, reviewed_head)
    assert_transition_allowed(
        workspace,
        "work_accept",
        work_id,
        actor=human_id,
        context={"reviewed_head": reviewed_head},
    )
    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    evidence = latest_for_work(workspace.evidence_runs, work_id)
    review = latest_for_work(workspace.review_verdicts, work_id)
    receipt = latest_for_work(workspace.receipts, work_id)
    if evidence is None or review is None:
        raise WorkspaceError(f"work {work_id} is missing evidence or review; cannot accept")
    human_decisions = _records(store, "human_decisions")
    acceptance_records = _records(store, "acceptance_records")
    decision_id = decision_id or f"HUMAN-DECISION-{work_id}-{human_id}"
    acceptance_id = acceptance_id or f"ACCEPTANCE-{work_id}-{human_id}"
    if _find(human_decisions, decision_id) is not None:
        raise WorkspaceError(f"human-decision already exists: {decision_id}")
    if _find(acceptance_records, acceptance_id) is not None:
        raise WorkspaceError(f"acceptance already exists: {acceptance_id}")
    qualified_count = _qualified_approval_count_after(workspace, work_id, human_id, reviewed_head)
    if qualified_count < work.required_approval_count:
        raise WorkspaceError(
            f"work {work_id} cannot be accepted: approval quorum would be "
            f"{qualified_count}/{work.required_approval_count}"
        )
    timestamp = _timestamp()
    decision = {
        "id": decision_id,
        "work_item_id": work_id,
        "human_id": human_id,
        "reviewed_head": reviewed_head,
        "decision": "accepted",
        "status": "accepted",
        "acceptance_mode": "human",
        "quorum_status": "met",
        "evidence_reference": evidence.id,
        "review_reference": review.id,
        "timestamp": timestamp,
    }
    acceptance = {
        "id": acceptance_id,
        "work_item_id": work_id,
        "human_id": human_id,
        "reviewed_head": reviewed_head,
        "status": "accepted",
        "decision_id": decision_id,
        "evidence_reference": evidence.id,
        "review_reference": review.id,
        "receipt_hash": receipt.receipt_hash if receipt else "",
        "authority_profile": authority_profile,
        "quorum_status": "met",
        "reason": reason,
        "accepted_at": timestamp,
    }
    human_decisions.append(decision)
    acceptance_records.append(acceptance)
    workspace = write_store(store)
    append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command=command or "work accept",
        action="accepted",
        object_type="acceptance",
        object_collection="acceptance_records",
        object_id=acceptance_id,
        actor=human_id,
        before=None,
        after=acceptance,
    )
    return MutationResult("accepted", "acceptance_records", acceptance_id, workspace.name)


def closeout_attempt(
    workspace_path: str,
    attempt_id: str,
    *,
    status: str,
    head_sha: str,
    cleanliness: str,
    changed_files: list[str],
    output_targets: list[str],
    allow_missing_evidence: bool,
    command: str = "",
    actor: str = "",
) -> MutationResult:
    store = load_store(workspace_path)
    attempts = _records(store, "attempts")
    attempt = _find(attempts, attempt_id)
    if attempt is None:
        raise WorkspaceError(f"attempt not found: {attempt_id}")
    if cleanliness.lower() not in {"clean", "pristine"}:
        raise WorkspaceError(f"attempt {attempt_id} cannot close out with cleanliness {cleanliness}")
    workspace = validate_data(store.data_path, store.data)
    assert_transition_allowed(
        workspace,
        "attempt_closeout",
        attempt_id,
        actor=str(attempt.get("actor") or actor),
        context={
            "head_sha": head_sha,
            "cleanliness": cleanliness,
            "allow_missing_evidence": allow_missing_evidence,
        },
    )
    before = deepcopy(attempt)
    attempt["status"] = status
    attempt["head_sha"] = head_sha
    commits = list(attempt.get("commits", []))
    if head_sha and (not commits or commits[-1] != head_sha):
        commits.append(head_sha)
    attempt["commits"] = commits
    attempt["cleanliness"] = cleanliness
    attempt["updated_at"] = _timestamp()
    if changed_files:
        attempt["changed_files"] = changed_files
    if output_targets:
        attempt["output_targets"] = output_targets
    workspace = validate_data(store.data_path, store.data)
    work_id = str(attempt.get("work_item_id") or "")
    if not allow_missing_evidence:
        matching_evidence = [
            evidence
            for evidence in workspace.evidence_runs
            if evidence.attempt_id == attempt_id and evidence.head_sha == head_sha
        ]
        if not matching_evidence:
            raise WorkspaceError(
                f"attempt {attempt_id} cannot close out without evidence for head {head_sha}"
            )
    workspace = write_store(store)
    append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command=command or "attempt closeout",
        action="closed-out",
        object_type="attempt",
        object_collection="attempts",
        object_id=attempt_id,
        actor=actor or str(attempt.get("actor") or ""),
        before=before,
        after=attempt,
    )
    return MutationResult("closed-out", "attempts", attempt_id, workspace.name, next_action=work_id)


def reconcile_agent_proof(
    workspace_path: str,
    *,
    work_id: str,
    palari_id: str,
    attempt_record: dict[str, Any],
    receipt_record: dict[str, Any],
    evidence_record: dict[str, Any],
    head_sha: str,
    changed_files: list[str],
    output_targets: list[str],
    crash_hook: Any | None = None,
) -> dict[str, Any]:
    """Atomically create or resume the agent-owned proof projection.

    Verification is deliberately outside this transaction. The caller must
    recheck its exact plan before entering. This function then commits the
    attempt, work binding, receipt, evidence, and attempt closeout through one
    workspace replacement and one governance-journal transaction.
    """

    from .governance_journal import MutationMetadata, utc_timestamp

    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    attempt_id = _record_id(attempt_record)
    receipt_id = _record_id(receipt_record)
    evidence_id = _record_id(evidence_record)
    steps: list[dict[str, str]] = []
    changed = False

    attempts = _records(store, "attempts")
    attempt = _find(attempts, attempt_id)
    if attempt is None:
        _assert_record_transition_allowed(store, "attempt", attempt_record)
        attempt = _prepare_record_for_create(store, "attempt", dict(attempt_record))
        attempts.append(attempt)
        steps.append({"step": "attempt-record", "id": attempt_id, "status": "created"})
        changed = True
    else:
        _assert_exact_resume(
            "attempt",
            attempt,
            attempt_record,
            ("work_item_id", "actor", "base_sha"),
        )
        steps.append({"step": "attempt-record", "id": attempt_id, "status": "resumed"})

    work_records = _records(store, "work_items")
    raw_work = _find(work_records, work_id)
    if raw_work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    before_work = deepcopy(raw_work)
    if raw_work.get("current_attempt") != attempt_id:
        raw_work["current_attempt"] = attempt_id
        steps.append({"step": "work-attempt-bind", "id": work_id, "status": "updated"})
        changed = True
    else:
        steps.append({"step": "work-attempt-bind", "id": work_id, "status": "resumed"})

    receipts = _records(store, "receipts")
    receipt = _find(receipts, receipt_id)
    if receipt is None:
        _assert_record_transition_allowed(store, "receipt", receipt_record)
        receipt = _prepare_record_for_create(store, "receipt", dict(receipt_record))
        receipts.append(receipt)
        steps.append({"step": "receipt-record", "id": receipt_id, "status": "created"})
        changed = True
    else:
        _assert_exact_resume(
            "receipt",
            receipt,
            receipt_record,
            ("work_item_id", "attempt_id", "actor", "outputs_created"),
        )
        steps.append({"step": "receipt-record", "id": receipt_id, "status": "resumed"})

    evidence_runs = _records(store, "evidence_runs")
    evidence = _find(evidence_runs, evidence_id)
    if evidence is None:
        _assert_record_transition_allowed(store, "evidence", evidence_record)
        evidence = _prepare_record_for_create(store, "evidence", dict(evidence_record))
        evidence_runs.append(evidence)
        steps.append({"step": "evidence-record", "id": evidence_id, "status": "created"})
        changed = True
    else:
        _assert_exact_resume(
            "evidence",
            evidence,
            evidence_record,
            ("work_item_id", "attempt_id", "head_sha", "status", "artifacts"),
        )
        steps.append({"step": "evidence-record", "id": evidence_id, "status": "resumed"})

    current_head = str(attempt.get("head_sha") or "")
    commits = list(attempt.get("commits", []))
    if not current_head and commits:
        current_head = str(commits[-1])
    if attempt.get("status") not in {"complete", "completed"} or current_head != head_sha:
        staged_workspace = validate_data(store.data_path, store.data)
        assert_transition_allowed(
            staged_workspace,
            "attempt_closeout",
            attempt_id,
            actor=palari_id,
            context={
                "head_sha": head_sha,
                "cleanliness": "clean",
                "allow_missing_evidence": False,
            },
        )
        attempt["status"] = "completed"
        attempt["head_sha"] = head_sha
        if not commits or commits[-1] != head_sha:
            commits.append(head_sha)
        attempt["commits"] = commits
        attempt["cleanliness"] = "clean"
        attempt["updated_at"] = _timestamp()
        attempt["changed_files"] = list(changed_files)
        attempt["output_targets"] = list(output_targets)
        steps.append({"step": "attempt-closeout", "id": attempt_id, "status": "closed-out"})
        changed = True
    else:
        steps.append({"step": "attempt-closeout", "id": attempt_id, "status": "resumed"})

    if changed:
        validate_data(store.data_path, store.data)
        metadata = MutationMetadata(
            command="agent advance",
            actor=palari_id,
            action="reconciled-agent-proof",
            timestamp=utc_timestamp(),
            objects=tuple(
                {
                    "type": kind,
                    "collection": collection,
                    "id": record_id,
                }
                for kind, collection, record_id in (
                    ("work", "work_items", work_id),
                    ("attempt", "attempts", attempt_id),
                    ("receipt", "receipts", receipt_id),
                    ("evidence", "evidence_runs", evidence_id),
                )
            ),
        )
        workspace = write_store(store, metadata=metadata, crash_hook=crash_hook)
        append_history_event(
            store.data_path,
            schema_version=workspace.schema_version,
            command="agent advance",
            action="reconciled-proof",
            object_type="work",
            object_collection="work_items",
            object_id=work_id,
            actor=palari_id,
            before=before_work,
            after=raw_work,
        )
    return {
        "attempt_id": attempt_id,
        "receipt_id": receipt_id,
        "evidence_id": evidence_id,
        "changed": changed,
        "steps": steps,
    }


def _assert_exact_resume(
    kind: str,
    current: dict[str, Any],
    expected: dict[str, Any],
    fields: tuple[str, ...],
) -> None:
    for field in fields:
        if current.get(field) != expected.get(field):
            raise WorkspaceError(
                f"existing {kind} {current.get('id', '')} conflicts on {field}"
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
    open_decisions = [
        decision.id
        for decision in workspace.decisions
        if decision.linked_work == work_id and decision.status == "open"
    ]
    if open_decisions:
        raise WorkspaceError(
            f"work {work_id} has open decisions: {', '.join(open_decisions)}; cannot accept"
        )
    work_detail = detail(workspace, work_id)
    if work_detail.get("coordination_warnings"):
        raise WorkspaceError(
            f"work {work_id} has scope coordination warnings; cannot accept"
        )
    attempt = current_attempt_for_work(work, workspace.attempts)
    evidence = latest_for_work(workspace.evidence_runs, work_id)
    review = latest_for_work(workspace.review_verdicts, work_id)
    if attempt is None:
        raise WorkspaceError(f"work {work_id} has no attempt; cannot accept")
    if attempt.cleanliness.lower() in {"dirty", "unclean"}:
        raise WorkspaceError(f"work {work_id} attempt {attempt.id} is dirty; cannot accept")
    attempt_head = _attempt_head(attempt)
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
    if evidence.manifest_hash:
        from .evidence_manifest import verify_evidence

        verification = verify_evidence(workspace, evidence.id, require_output_coverage=True)
        if not verification["ok"]:
            raise WorkspaceError(
                f"work {work_id} evidence manifest verification failed; cannot accept"
            )
    from .governance_binding import current_review_binding_errors

    binding_errors = current_review_binding_errors(
        workspace, review, require_output_coverage=True
    )
    if binding_errors:
        raise WorkspaceError(
            f"work {work_id} exact review proof is stale: {binding_errors[0]}; cannot accept"
        )


def _prepare_record_for_create(
    store: WorkspaceStore,
    kind: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    if kind == "attempt":
        stamped = dict(record)
        if not stamped.get("started_at"):
            stamped["started_at"] = _timestamp()
        return stamped
    if kind == "evidence":
        from .evidence_manifest import stamp_evidence_record

        stamped = dict(record)
        if not stamped.get("timestamp"):
            stamped["timestamp"] = _timestamp()
        receipt = _latest_raw_for_attempt(
            _records(store, "receipts"),
            str(stamped.get("work_item_id") or ""),
            str(stamped.get("attempt_id") or ""),
        )
        if receipt and receipt.get("receipt_hash") and not stamped.get("receipt_hash"):
            stamped["receipt_hash"] = receipt["receipt_hash"]
        return stamp_evidence_record(
            stamped,
            store.data_path.parent,
            attempts=_records(store, "attempts"),
        )
    if kind == "receipt":
        from .evidence_manifest import stamp_receipt_record

        stamped = dict(record)
        if not stamped.get("timestamp"):
            stamped["timestamp"] = _timestamp()
        return stamp_receipt_record(stamped, _records(store, "receipts"))
    if kind == "review":
        stamped = dict(record)
        if not stamped.get("timestamp"):
            stamped["timestamp"] = _timestamp()
        if stamped.get("verdict") == "accept-ready":
            workspace = validate_data(store.data_path, store.data)
            from .governance_binding import current_review_binding, review_proof_hash

            binding, errors = current_review_binding(
                workspace,
                str(stamped.get("work_item_id") or ""),
                require_output_coverage=True,
            )
            if errors:
                raise WorkspaceError(f"cannot bind accept-ready review: {errors[0]}")
            stamped.update(binding)
            stamped["proof_hash"] = review_proof_hash(stamped)
        return stamped
    if kind == "human-decision":
        stamped = dict(record)
        if not stamped.get("timestamp"):
            stamped["timestamp"] = _timestamp()
        return stamped
    if kind == "outcome":
        stamped = dict(record)
        if not stamped.get("timestamp"):
            stamped["timestamp"] = _timestamp()
        return stamped
    return record


def _prepare_record_for_update(
    store: WorkspaceStore,
    kind: str,
    record: dict[str, Any],
    updates: dict[str, Any],
) -> None:
    if kind == "human-decision" and set(updates) & {"decision", "status"}:
        if "timestamp" not in updates:
            record["timestamp"] = _timestamp()
    if kind == "evidence":
        from .evidence_manifest import stamp_evidence_record

        if "artifacts" in updates and "artifact_hashes" not in updates:
            record.pop("artifact_hashes", None)
        record.update(
            stamp_evidence_record(
                record,
                store.data_path.parent,
                attempts=_records(store, "attempts"),
            )
        )
    if kind == "receipt":
        from .evidence_manifest import stamp_receipt_record

        other_receipts = [
            item for item in _records(store, "receipts") if item.get("id") != record.get("id")
        ]
        record.update(stamp_receipt_record(record, other_receipts))
    if (
        kind == "review"
        and record.get("verdict") == "accept-ready"
        and set(updates) & TRANSITION_UPDATE_FIELDS["review"]
    ):
        workspace = validate_data(store.data_path, store.data)
        from .governance_binding import current_review_binding, review_proof_hash

        binding, errors = current_review_binding(
            workspace,
            str(record.get("work_item_id") or ""),
            require_output_coverage=True,
        )
        if errors:
            raise WorkspaceError(f"cannot bind accept-ready review: {errors[0]}")
        record.update(binding)
        record["proof_hash"] = review_proof_hash(record)


def _assert_record_transition_allowed(
    store: WorkspaceStore,
    kind: str,
    record: dict[str, Any],
    *,
    allow_existing: bool = False,
) -> None:
    if kind not in {"evidence", "review"}:
        return
    workspace = validate_data(store.data_path, store.data)
    if kind == "evidence":
        assert_transition_allowed(
            workspace,
            "evidence_record",
            str(record.get("id") or ""),
            actor=str(record.get("actor") or ""),
            context={
                "work_item_id": str(record.get("work_item_id") or ""),
                "attempt_id": str(record.get("attempt_id") or ""),
                "head_sha": str(record.get("head_sha") or ""),
                "allow_existing": allow_existing,
            },
        )
        return
    assert_transition_allowed(
        workspace,
        "review_record",
        str(record.get("id") or ""),
        actor=str(record.get("reviewer") or ""),
        context={
            "work_item_id": str(record.get("work_item_id") or ""),
            "reviewed_head": str(record.get("reviewed_head") or ""),
            "verdict": str(record.get("verdict") or ""),
            "allow_existing": allow_existing,
        },
    )


def _record_update_needs_transition(kind: str, updates: dict[str, Any]) -> bool:
    return bool(set(updates) & TRANSITION_UPDATE_FIELDS.get(kind, set()))


def _ensure_acceptance_record_for_completion(
    store: WorkspaceStore,
    workspace: Any,
    work_id: str,
    actor: str,
) -> None:
    work = workspace.work_item(work_id)
    if work is None or work.risk in {"R1", "R2"} and work.required_approval_count == 0:
        return
    if any(item.get("work_item_id") == work_id for item in _records(store, "acceptance_records")):
        return
    review = latest_for_work(workspace.review_verdicts, work_id)
    evidence = latest_for_work(workspace.evidence_runs, work_id)
    receipt = latest_for_work(workspace.receipts, work_id)
    if review is None or evidence is None:
        return
    matching_decisions = [
        decision
        for decision in workspace.human_decisions
        if decision.work_item_id == work_id
        and decision.reviewed_head == review.reviewed_head
        and decision.review_reference == review.id
        and decision.evidence_reference == evidence.id
        and _is_approval(decision)
    ]
    if not matching_decisions:
        return
    decision = max(matching_decisions, key=_decision_order_key)
    acceptance_id = f"ACCEPTANCE-{work_id}-{decision.human_id}"
    if _find(_records(store, "acceptance_records"), acceptance_id) is not None:
        return
    _records(store, "acceptance_records").append(
        {
            "id": acceptance_id,
            "work_item_id": work_id,
            "human_id": decision.human_id,
            "reviewed_head": review.reviewed_head,
            "status": "accepted",
            "decision_id": decision.id,
            "evidence_reference": evidence.id,
            "review_reference": review.id,
            "receipt_hash": receipt.receipt_hash if receipt else "",
            "authority_profile": "team-safe",
            "quorum_status": "met",
            "reason": actor or "completion gate",
            "accepted_at": _timestamp(),
        }
    )


def _qualified_approval_count_after(
    workspace: Any,
    work_id: str,
    human_id: str,
    reviewed_head: str,
) -> int:
    work = workspace.work_item(work_id)
    if work is None:
        return 0
    humans_by_id = {human.id: human for human in workspace.humans}
    review = latest_for_work(workspace.review_verdicts, work_id)
    evidence = latest_for_work(workspace.evidence_runs, work_id)
    if (
        review is None
        or evidence is None
        or review.reviewed_head != reviewed_head
        or review.evidence_reference != evidence.id
    ):
        return 0
    incoming_human = humans_by_id.get(human_id)
    seen: set[str] = set()
    if not work.required_approval_capability or (
        incoming_human is not None
        and work.required_approval_capability in incoming_human.approval_capabilities
    ):
        seen.add(human_id)
    latest_by_human: dict[str, Any] = {}
    for decision in workspace.human_decisions:
        if decision.work_item_id != work_id or decision.reviewed_head != reviewed_head:
            continue
        previous = latest_by_human.get(decision.human_id)
        if previous is None or _decision_order_key(decision) > _decision_order_key(previous):
            latest_by_human[decision.human_id] = decision
    for decision in latest_by_human.values():
        if not _is_approval(decision):
            continue
        if (
            decision.review_reference != review.id
            or decision.evidence_reference != evidence.id
        ):
            continue
        human = humans_by_id.get(decision.human_id)
        if work.required_approval_capability and (
            human is None or work.required_approval_capability not in human.approval_capabilities
        ):
            continue
        seen.add(decision.human_id)
    return len(seen)


def _decision_order_key(decision: Any) -> tuple[datetime, str]:
    try:
        timestamp = datetime.fromisoformat(
            str(getattr(decision, "timestamp", "")).replace("Z", "+00:00")
        )
    except ValueError:
        timestamp = datetime.min.replace(tzinfo=timezone.utc)
    return (timestamp, str(getattr(decision, "id", "")))


def _is_approval(decision: Any) -> bool:
    return decision.status in {"accepted", "approved"} and decision.decision in {
        "accepted",
        "approved",
    }


def _latest_raw_for_attempt(
    records: list[dict[str, Any]], work_id: str, attempt_id: str
) -> dict[str, Any] | None:
    candidates = [
        record
        for record in records
        if record.get("work_item_id") == work_id and record.get("attempt_id") == attempt_id
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=record_time_key,
    )


def _reject_generic_trust_transition(
    kind: str, record_id: str, record: dict[str, Any], updates: dict[str, Any]
) -> None:
    if kind == "work" and str(updates.get("status") or "") in {"completed", "closed", "done"}:
        raise WorkspaceError(
            f"work {record_id} terminal status must use `palari work complete`"
        )
    if kind == "attempt" and set(updates) & {
        "status",
        "head_sha",
        "commits",
        "cleanliness",
        "changed_files",
        "output_targets",
    }:
        raise WorkspaceError(
            f"attempt {record_id} trust fields must use `palari attempt closeout`"
        )
    if kind == "review" and record.get("binding_version"):
        raise WorkspaceError(
            f"review {record_id} is exact-proof-bound and immutable; record a new review"
        )


def _attempt_head(attempt: Any) -> str:
    return attempt.head_sha or (attempt.commits[-1] if attempt.commits else "")


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


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
