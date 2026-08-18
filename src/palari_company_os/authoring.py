from __future__ import annotations

from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .record_order import record_time_key
from .store import WorkspaceStore, load_store, validate_data, write_store
from .transition_checks import assert_transition_allowed
from .workspace import WorkspaceError, latest_for_work


class ReconciliationStateChanged(WorkspaceError):
    """The workspace no longer matches the proof plan verified by the caller."""


_WORKSPACE_CAS_MESSAGES = {
    "workspace file appeared before write; retry command",
    "workspace file was removed before write; retry command",
    "workspace changed since it was loaded; retry command",
}


def _assert_reconciliation_git_state(
    proof_root: str,
    governance_workspace_path: str,
    artifacts: list[str],
    expected_git_head: str,
    expected_artifact_hashes: list[dict[str, str]],
) -> None:
    from .evidence_manifest import git_artifact_state

    delete_intents = [
        {"path": item["path"], "intent": "delete"}
        for item in expected_artifact_hashes
        if item.get("status") == "absent"
        and item.get("sha256") == "sha256:absent"
        and isinstance(item.get("path"), str)
    ]
    artifact_state = git_artifact_state(
        Path(proof_root),
        artifacts,
        governance_workspace_path=Path(governance_workspace_path),
        path_intents=delete_intents,
    )
    if (
        artifact_state["head_sha"] != expected_git_head
        or not artifact_state["clean"]
        or artifact_state["artifact_hashes"] != expected_artifact_hashes
    ):
        raise ReconciliationStateChanged(
            "Git head, tracked cleanliness, or artifact bytes changed after verification"
        )


@dataclass(frozen=True)
class MutationResult:
    action: str
    collection: str
    record_id: str
    workspace: str
    next_action: str = ""


_MUTABLE_COLLECTIONS = {
    "palari": "palaris",
    "work": "work_items",
    "evidence": "evidence_runs",
    "review": "review_verdicts",
}
_TRUST_UPDATE_FIELDS = {
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
    "review": {"work_item_id", "reviewed_head", "reviewer", "verdict"},
}


def create_record(
    workspace_path: str,
    kind: str,
    record: dict[str, Any],
    *,
    command: str = "",
    actor: str = "",
) -> MutationResult:
    """Narrow recorder used by focused product flows and governance tests."""

    try:
        collection = _MUTABLE_COLLECTIONS[kind]
    except KeyError as exc:
        raise WorkspaceError(f"unsupported internal record type: {kind}") from exc
    store = load_store(workspace_path)
    records = _records(store, collection)
    record_id = _record_id(record)
    if _find(records, record_id) is not None:
        raise WorkspaceError(f"{kind} already exists: {record_id}")
    _assert_record_transition_allowed(store, kind, record)
    records.append(_prepare_record_for_create(store, kind, dict(record)))
    workspace = write_store(
        store,
        metadata=_mutation_metadata(
            command or f"{kind} create",
            _event_actor(record, actor),
            "created",
            ((kind, collection, record_id),),
        ),
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
    """Internal fixture helper for exercising authority-race detection."""

    try:
        collection = _MUTABLE_COLLECTIONS[kind]
    except KeyError as exc:
        raise WorkspaceError(f"unsupported internal record type: {kind}") from exc
    store = load_store(workspace_path)
    record = _find(_records(store, collection), record_id)
    if record is None:
        raise WorkspaceError(f"{kind} not found: {record_id}")
    _reject_generic_trust_transition(kind, record_id, record, updates)
    merged = dict(record)
    merged.update(updates)
    if set(updates) & _TRUST_UPDATE_FIELDS.get(kind, set()):
        _assert_record_transition_allowed(store, kind, merged, allow_existing=True)
    record.update(updates)
    _prepare_record_for_update(store, kind, record, updates)
    workspace = write_store(
        store,
        metadata=_mutation_metadata(
            command or f"{kind} update",
            _event_actor(record, actor),
            "updated",
            ((kind, collection, record_id),),
        ),
    )
    return MutationResult("updated", collection, record_id, workspace.name)


def create_human_decision(
    workspace_path: str,
    record: dict[str, Any],
    *,
    command: str = "",
    actor: str = "",
    automatic_convergence: bool = True,
) -> MutationResult:
    """Internal setup path retained for governance integration tests."""

    record = dict(record)
    record.setdefault("timestamp", _timestamp())
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    work_id = str(record.get("work_item_id") or "")
    decision = str(record.get("decision") or "")
    if decision in {"accepted", "approved"}:
        transition = assert_transition_allowed(
            workspace,
            "human_decision_accept",
            str(record.get("id") or ""),
            actor=str(record.get("human_id") or ""),
            context={
                key: record.get(key, "")
                for key in (
                    "work_item_id",
                    "reviewed_head",
                    "timestamp",
                    "acceptance_mode",
                    "decision",
                    "status",
                    "evidence_reference",
                    "review_reference",
                )
            },
        )
        if transition.authority_candidate is not None:
            record["quorum_status"] = (
                "met" if transition.authority_candidate.quorum_met else "pending"
            )
    record_id = _record_id(record)
    records = _records(store, "human_decisions")
    if _find(records, record_id) is not None:
        raise WorkspaceError(f"human-decision already exists: {record_id}")
    records.append(record)
    workspace = write_store(
        store,
        metadata=_mutation_metadata(
            command or "human-decision record",
            _event_actor(record, actor),
            "created",
            (("human-decision", "human_decisions", record_id),),
        ),
    )
    result = MutationResult("created", "human_decisions", record_id, workspace.name)
    if automatic_convergence and decision in {"accepted", "approved"}:
        from .governance_convergence import converge_work_item

        convergence = converge_work_item(workspace_path, work_id, actor=actor)
        result = MutationResult(
            result.action,
            result.collection,
            result.record_id,
            result.workspace,
            str(convergence.get("message") or ""),
        )
    return result


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
    current = workspace.work_item(work_id)
    if current is None:
        raise WorkspaceError(f"work not found: {work_id}")
    if current.terminal_disposition:
        raise WorkspaceError(
            f"work {work_id} was {current.terminal_disposition} and cannot be "
            "completed; create or follow an explicit successor task"
        )
    if current.status in {"completed", "closed", "done"}:
        return MutationResult("completed", "work_items", work_id, workspace.name)
    acceptance_ids_before = {
        str(item.get("id") or "") for item in _records(store, "acceptance_records")
    }
    _append_projected_acceptance_for_completion(store, workspace, work_id, actor)
    projected_workspace = validate_data(store.data_path, store.data)
    assert_work_completion_ready(projected_workspace, work_id, actor=actor)
    work = _find(_records(store, "work_items"), work_id)
    if work is None:
        raise WorkspaceError(f"work not found: {work_id}")
    work["status"] = status
    objects: list[tuple[str, str, str]] = [("work", "work_items", work_id)]
    objects.extend(
        ("acceptance", "acceptance_records", str(item.get("id") or ""))
        for item in _records(store, "acceptance_records")
        if str(item.get("id") or "") not in acceptance_ids_before
    )
    workspace = write_store(
        store,
        metadata=_mutation_metadata(
            command or "work complete",
            _event_actor(work, actor),
            "completed",
            tuple(objects),
        ),
    )
    return MutationResult("completed", "work_items", work_id, workspace.name)


def assert_work_completion_ready(
    workspace: Any,
    work_id: str,
    *,
    actor: str = "",
) -> dict[str, Any]:
    """Apply the authoritative completion checks without mutating workspace state."""

    transition = assert_transition_allowed(
        workspace,
        "work_complete",
        work_id,
        actor=actor,
    )
    return transition.to_dict()


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
    proof_timestamp: str,
    expected_workspace_digest: str,
    expected_git_head: str,
    expected_artifact_hashes: list[dict[str, str]],
    crash_hook: Any | None = None,
) -> dict[str, Any]:
    """Atomically create or resume the agent-owned proof projection.

    Verification is deliberately outside this transaction. The caller must
    recheck its exact plan before entering. This function then commits the
    attempt, work binding, receipt, evidence, and attempt closeout through one
    workspace replacement and one governance-journal transaction.
    """

    from .governance_journal import MutationMetadata, workspace_digest

    store = load_store(workspace_path)
    if workspace_digest(store.data) != expected_workspace_digest:
        raise ReconciliationStateChanged(
            "workspace changed after the proof plan was verified"
        )
    artifacts = list(evidence_record.get("artifacts") or [])
    proof_root = str(attempt_record.get("workspace_path") or workspace_path)
    _assert_reconciliation_git_state(
        proof_root,
        workspace_path,
        artifacts,
        expected_git_head,
        expected_artifact_hashes,
    )
    if evidence_record.get("artifact_hashes") != expected_artifact_hashes:
        raise ReconciliationStateChanged(
            "evidence artifact hashes do not match the verified proof plan"
        )
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
        new_attempt = dict(attempt_record)
        new_attempt["started_at"] = proof_timestamp
        attempt = _prepare_record_for_create(store, "attempt", new_attempt)
        attempts.append(attempt)
        steps.append({"step": "attempt-record", "id": attempt_id, "status": "created"})
        changed = True
    else:
        _assert_exact_resume(
            "attempt",
            attempt,
            attempt_record,
            ("work_item_id", "actor", "base_sha", "allowed_paths"),
        )
        steps.append({"step": "attempt-record", "id": attempt_id, "status": "resumed"})

    work_records = _records(store, "work_items")
    raw_work = _find(work_records, work_id)
    if raw_work is None:
        raise WorkspaceError(f"work not found: {work_id}")
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
        new_receipt = dict(receipt_record)
        new_receipt["timestamp"] = proof_timestamp
        receipt = _prepare_record_for_create(store, "receipt", new_receipt)
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
        new_evidence = dict(evidence_record)
        new_evidence["timestamp"] = proof_timestamp
        evidence = _prepare_record_for_create(store, "evidence", new_evidence)
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

    staged_workspace = validate_data(store.data_path, store.data)
    from .evidence_manifest import verify_evidence

    evidence_verification = verify_evidence(
        staged_workspace,
        evidence_id,
    )
    if not evidence_verification["ok"]:
        missing = [
            item["path"]
            for item in evidence_verification["computed_artifact_hashes"]
            if item.get("status") != "present"
        ]
        detail = f": {', '.join(missing)}" if missing else ""
        raise WorkspaceError(
            f"agent proof evidence manifest verification failed{detail}"
        )

    current_head = str(attempt.get("head_sha") or "")
    commits = list(attempt.get("commits", []))
    if not current_head and commits:
        current_head = str(commits[-1])
    if attempt.get("status") not in {"complete", "completed"} or current_head != head_sha:
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
        attempt["updated_at"] = proof_timestamp
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
            timestamp=proof_timestamp,
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
            reason="receipt-action:"
            + str((receipt.get("actions_taken") or [""])[0]),
        )
        _assert_reconciliation_git_state(
            proof_root,
            workspace_path,
            artifacts,
            expected_git_head,
            expected_artifact_hashes,
        )
        try:
            workspace = write_store(store, metadata=metadata, crash_hook=crash_hook)
        except WorkspaceError as exc:
            if str(exc) in _WORKSPACE_CAS_MESSAGES:
                raise ReconciliationStateChanged(
                    "workspace changed before the proof transaction acquired its writer lock"
                ) from exc
            raise
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
        stamped.pop("review_binding_digest", None)
        if not stamped.get("timestamp"):
            stamped["timestamp"] = _timestamp()
        workspace = validate_data(store.data_path, store.data)
        from .governance_binding import current_review_binding, review_proof_hash

        binding, errors = current_review_binding(
            workspace,
            str(stamped.get("work_item_id") or ""),
        )
        if errors:
            raise WorkspaceError(f"cannot bind review: {errors[0]}")
        stamped.update(binding)
        stamped["proof_hash"] = review_proof_hash(stamped)
        return stamped
    return record


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
            "review_binding_digest": str(
                record.get("review_binding_digest") or ""
            ),
            "allow_existing": allow_existing,
        },
    )


def _prepare_record_for_update(
    store: WorkspaceStore,
    kind: str,
    record: dict[str, Any],
    updates: dict[str, Any],
) -> None:
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
    if (
        kind == "review"
        and record.get("verdict") == "accept-ready"
        and set(updates) & _TRUST_UPDATE_FIELDS["review"]
    ):
        workspace = validate_data(store.data_path, store.data)
        from .governance_binding import current_review_binding, review_proof_hash

        binding, errors = current_review_binding(
            workspace,
            str(record.get("work_item_id") or ""),
        )
        if errors:
            raise WorkspaceError(f"cannot bind accept-ready review: {errors[0]}")
        record.update(binding)
        record["proof_hash"] = review_proof_hash(record)


def _append_projected_acceptance_for_completion(
    store: WorkspaceStore,
    workspace: Any,
    work_id: str,
    actor: str,
) -> None:
    work = workspace.work_item(work_id)
    if work is None:
        return
    receipt = latest_for_work(workspace.receipts, work_id)
    from .pcaw_workspace import evaluate_workspace_completion_authority

    accepted_at = _timestamp()
    projection = evaluate_workspace_completion_authority(
        workspace,
        work_id,
        accepted_at=accepted_at,
    )
    acceptance = projection.acceptance
    if acceptance is None or not projection.ready:
        return
    acceptance_id = acceptance.id
    if _find(_records(store, "acceptance_records"), acceptance_id) is not None:
        return
    _records(store, "acceptance_records").append(
        {
            "id": acceptance_id,
            "work_item_id": work_id,
            "human_id": acceptance.human_id,
            "reviewed_head": acceptance.reviewed_head,
            "status": "accepted",
            "decision_id": acceptance.decision_id,
            "evidence_reference": acceptance.evidence_id,
            "review_reference": acceptance.review_id,
            "receipt_hash": receipt.receipt_hash if receipt else "",
            "authority_profile": "team-safe",
            "quorum_status": "met",
            "reason": actor or "completion gate",
            "accepted_at": accepted_at,
        }
    )


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
    kind: str,
    record_id: str,
    record: dict[str, Any],
    updates: dict[str, Any],
) -> None:
    if kind == "review" and record.get("binding_version"):
        raise WorkspaceError(
            f"review {record_id} is exact-proof-bound and immutable; record a new review"
        )


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


def _mutation_metadata(
    command: str,
    actor: str,
    action: str,
    objects: tuple[tuple[str, str, str], ...],
) -> Any:
    from .governance_journal import MutationMetadata, utc_timestamp
    from .mutation_context import current_mutation_identity

    _, context_actor, _ = current_mutation_identity()

    return MutationMetadata(
        command=command,
        actor=actor or context_actor,
        action=action,
        timestamp=utc_timestamp(),
        objects=tuple(
            {"type": kind, "collection": collection, "id": object_id}
            for kind, collection, object_id in objects
        ),
    )


def _event_actor(record: dict[str, Any], actor: str) -> str:
    return actor or str(
        record.get("human_id")
        or record.get("reviewer")
        or record.get("actor")
        or ""
    )


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
