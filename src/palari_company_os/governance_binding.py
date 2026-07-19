from __future__ import annotations

import hashlib
import json
from typing import Any

from .evidence_manifest import (
    receipt_hash,
    stored_evidence_integrity_errors,
    verify_evidence,
)
from .governance_journal import JournalVerificationContext
from .workspace import current_attempt_for_work, latest_for_work


BINDING_VERSION = "palari.review_binding.v1"
HASH_PREFIX = "sha256:"
TERMINAL_ATTEMPT_STATUSES = {"complete", "completed"}
CLEAN_ATTEMPT_STATES = {"clean", "pristine"}


def current_review_binding(
    workspace: Any,
    work_id: str,
    *,
    require_output_coverage: bool | None = None,
    journal_context: JournalVerificationContext | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Return the exact current proof binding and fail-closed eligibility errors."""
    return _current_review_binding(
        workspace,
        work_id,
        inspect_external=True,
        require_output_coverage=require_output_coverage,
        journal_context=journal_context,
    )


def _current_review_binding(
    workspace: Any,
    work_id: str,
    *,
    inspect_external: bool,
    require_output_coverage: bool | None,
    journal_context: JournalVerificationContext | None,
) -> tuple[dict[str, str], list[str]]:
    work = workspace.work_item(work_id)
    if work is None:
        return {}, [f"work not found: {work_id}"]

    attempt = current_attempt_for_work(work, workspace.attempts)
    if attempt is None:
        return {}, [f"work {work_id} has no current attempt"]

    errors: list[str] = []
    if not work.current_attempt or attempt.id != work.current_attempt:
        errors.append(f"work {work_id} does not identify attempt {attempt.id} as current")
    if attempt.status not in TERMINAL_ATTEMPT_STATUSES:
        errors.append(f"attempt {attempt.id} is {attempt.status}, not complete")
    if attempt.cleanliness.lower() not in CLEAN_ATTEMPT_STATES:
        errors.append(f"attempt {attempt.id} is not recorded clean")
    head_sha = _attempt_head(attempt)
    if not head_sha:
        errors.append(f"attempt {attempt.id} has no exact head")

    evidence = _latest_for_attempt(workspace.evidence_runs, work_id, attempt.id)
    receipt = _latest_for_attempt(workspace.receipts, work_id, attempt.id)
    if evidence is None:
        errors.append(f"attempt {attempt.id} has no evidence")
    if receipt is None:
        errors.append(f"attempt {attempt.id} has no receipt")
    if evidence is not None:
        errors.extend(
            _evidence_errors(
                workspace,
                attempt,
                evidence,
                receipt,
                inspect_external=inspect_external,
                require_output_coverage=require_output_coverage,
                journal_context=journal_context,
            )
        )
    if receipt is not None:
        errors.extend(_receipt_errors(receipt))

    if evidence is None or receipt is None:
        return {}, _unique(errors)
    binding = {
        "binding_version": BINDING_VERSION,
        "attempt_id": attempt.id,
        "attempt_hash": attempt_state_hash(attempt),
        "evidence_reference": evidence.id,
        "evidence_manifest_hash": evidence.manifest_hash,
        "receipt_reference": receipt.id,
        "receipt_hash": receipt.receipt_hash,
        "work_contract_hash": work_contract_hash(work),
    }
    return binding, _unique(errors)


def review_binding_integrity_errors(workspace: Any, review: Any) -> list[str]:
    """Validate a stored binding without requiring it to match the current contract."""
    if not review.binding_version:
        return [f"review {review.id} has no exact proof binding"]
    if review.binding_version != BINDING_VERSION:
        return [f"review {review.id} uses unsupported binding {review.binding_version}"]

    errors: list[str] = []
    attempt = next((item for item in workspace.attempts if item.id == review.attempt_id), None)
    evidence = next(
        (item for item in workspace.evidence_runs if item.id == review.evidence_reference), None
    )
    receipt = next(
        (item for item in workspace.receipts if item.id == review.receipt_reference), None
    )
    if attempt is None:
        errors.append(f"review {review.id} references missing attempt {review.attempt_id}")
    elif attempt.work_item_id != review.work_item_id:
        errors.append(f"review {review.id} attempt belongs to {attempt.work_item_id}")
    elif review.attempt_hash != attempt_state_hash(attempt):
        errors.append(f"review {review.id} attempt state changed after review")
    if evidence is None:
        errors.append(
            f"review {review.id} references missing evidence {review.evidence_reference}"
        )
    else:
        if evidence.work_item_id != review.work_item_id or evidence.attempt_id != review.attempt_id:
            errors.append(f"review {review.id} evidence does not match its work and attempt")
        if evidence.manifest_hash != review.evidence_manifest_hash:
            errors.append(f"review {review.id} evidence manifest changed after review")
        if evidence.head_sha != review.reviewed_head:
            errors.append(f"review {review.id} evidence head does not match reviewed head")
    if receipt is None:
        errors.append(f"review {review.id} references missing receipt {review.receipt_reference}")
    else:
        if receipt.work_item_id != review.work_item_id or receipt.attempt_id != review.attempt_id:
            errors.append(f"review {review.id} receipt does not match its work and attempt")
        if receipt.receipt_hash != review.receipt_hash:
            errors.append(f"review {review.id} receipt changed after review")

    if not review.proof_hash or review.proof_hash != review_proof_hash(review):
        errors.append(f"review {review.id} proof hash is missing or malformed")
    return errors


def current_review_binding_errors(
    workspace: Any,
    review: Any,
    *,
    require_output_coverage: bool | None = None,
    journal_context: JournalVerificationContext | None = None,
) -> list[str]:
    """Require a structurally sound review to match the current proof and contract."""
    errors = review_binding_integrity_errors(workspace, review)
    binding, current_errors = current_review_binding(
        workspace,
        review.work_item_id,
        require_output_coverage=require_output_coverage,
        journal_context=journal_context,
    )
    errors.extend(current_errors)
    if binding:
        for field, expected in binding.items():
            if getattr(review, field, "") != expected:
                errors.append(f"review {review.id} {field} is stale")
    return _unique(errors)


def recorded_current_proof_errors(workspace: Any, work_id: str) -> list[str]:
    """Check current proof records without reading files, Git, or the journal.

    This is a projection boundary, not completion authority.  It establishes
    only that the stored current attempt, receipt, and versioned evidence form
    one structurally exact proof.  Mutation and portable proof boundaries must
    still call :func:`current_review_binding` and re-observe external state.
    """

    _, errors = _current_review_binding(
        workspace,
        work_id,
        inspect_external=False,
        require_output_coverage=True,
        journal_context=None,
    )
    return errors


def recorded_current_review_binding_errors(workspace: Any, review: Any) -> list[str]:
    """Check current exact-review metadata without reading files or Git state.

    This is deliberately weaker than :func:`current_review_binding_errors`: it
    proves that the stored receipt, evidence manifest, attempt, contract, and
    review bind to one another, but it does not re-observe artifact bytes or
    journal continuity.  Read-only projections may use the result to preserve
    an existing binding; mutation and proof-export boundaries must still run
    the full current check.
    """

    errors = review_binding_integrity_errors(workspace, review)
    binding, current_errors = _current_review_binding(
        workspace,
        review.work_item_id,
        inspect_external=False,
        require_output_coverage=True,
        journal_context=None,
    )
    errors.extend(current_errors)
    if binding:
        for field, expected in binding.items():
            if getattr(review, field, "") != expected:
                errors.append(f"review {review.id} {field} is stale")
    return _unique(errors)


def work_contract_hash(work: Any) -> str:
    payload = {
        "id": work.id,
        "goal": work.goal,
        "palari": work.palari,
        "workbench_id": work.workbench_id,
        "parent_work_item_id": work.parent_work_item_id,
        "dependency_ids": sorted(work.dependency_ids),
        "risk": work.risk,
        "intensity": work.intensity,
        "scope": work.scope,
        "allowed_resources": sorted(work.allowed_resources),
        "allowed_sources": sorted(work.allowed_sources),
        "allowed_actions": sorted(work.allowed_actions),
        "output_targets": sorted(work.output_targets),
        "forbidden_actions": sorted(work.forbidden_actions),
        "acceptance_target": work.acceptance_target,
        "verification_expectations": list(work.verification_expectations),
        "required_approval_count": work.required_approval_count,
        "required_approval_capability": work.required_approval_capability,
        "conflict_targets": sorted(work.conflict_targets),
        "parallel_policy": work.parallel_policy,
    }
    path_intents = getattr(work, "path_intents", [])
    if path_intents:
        payload["path_intents"] = sorted(
            (
                {"path": str(item.get("path", "")), "intent": str(item.get("intent", ""))}
                for item in path_intents
                if isinstance(item, dict)
            ),
            key=lambda item: (item["path"], item["intent"]),
        )
    return _stable_hash(payload)


def attempt_state_hash(attempt: Any) -> str:
    payload = {
        "id": attempt.id,
        "work_item_id": attempt.work_item_id,
        "actor": attempt.actor,
        "status": attempt.status,
        "branch": attempt.branch,
        "workspace_path": attempt.workspace_path,
        "base_sha": attempt.base_sha,
        "head_sha": attempt.head_sha,
        "commits": list(attempt.commits),
        "changed_files": sorted(attempt.changed_files),
        "allowed_paths": sorted(attempt.allowed_paths),
        "forbidden_paths": sorted(attempt.forbidden_paths),
        "cleanliness": attempt.cleanliness,
        "result": attempt.result,
        "output_targets": sorted(attempt.output_targets),
    }
    return _stable_hash(payload)


def review_proof_hash(review: Any) -> str:
    """Bind exact proof inputs and the reviewer-authored verdict context."""

    payload = {
        **{
            key: _record_value(review, key)
            for key in (
                "binding_version",
                "attempt_id",
                "attempt_hash",
                "evidence_reference",
                "evidence_manifest_hash",
                "receipt_reference",
                "receipt_hash",
                "work_contract_hash",
            )
        },
        "id": _record_value(review, "id"),
        "work_item_id": _record_value(review, "work_item_id"),
        "reviewed_head": _record_value(review, "reviewed_head"),
        "reviewer": _record_value(review, "reviewer"),
        "verdict": _record_value(review, "verdict"),
        "findings": _record_value(review, "findings", []),
        "checks_inspected": _record_value(review, "checks_inspected", []),
        "residual_risks": _record_value(review, "residual_risks", []),
        "timestamp": _record_value(review, "timestamp"),
    }
    return _stable_hash(payload)


def _evidence_errors(
    workspace: Any,
    attempt: Any,
    evidence: Any,
    receipt: Any | None,
    *,
    inspect_external: bool,
    require_output_coverage: bool | None,
    journal_context: JournalVerificationContext | None,
) -> list[str]:
    errors: list[str] = []
    if evidence.status != "passed":
        errors.append(f"evidence {evidence.id} is {evidence.status}, not passed")
    if evidence.head_sha != _attempt_head(attempt):
        errors.append(f"evidence {evidence.id} is stale for attempt {attempt.id}")
    if not evidence.commands:
        errors.append(f"evidence {evidence.id} has no verification commands")
    if not evidence.summary.strip():
        errors.append(f"evidence {evidence.id} has no verification summary")
    if not evidence.timestamp:
        errors.append(f"evidence {evidence.id} has no timestamp")
    if not evidence.manifest_hash:
        errors.append(f"evidence {evidence.id} has no manifest hash")
    elif inspect_external:
        verification = verify_evidence(
            workspace,
            evidence.id,
            require_output_coverage=require_output_coverage,
            journal_context=journal_context,
        )
        if not verification["ok"]:
            errors.append(f"evidence {evidence.id} manifest verification failed")
    else:
        work = workspace.work_item(evidence.work_item_id)
        errors.extend(
            stored_evidence_integrity_errors(
                evidence,
                receipt,
                path_intents=getattr(work, "path_intents", ()),
                require_output_coverage=True,
                require_version=True,
            )
        )
    artifact_statuses = {
        str(item.get("path", "")): str(item.get("status", ""))
        for item in evidence.artifact_hashes
    }
    work = workspace.work_item(evidence.work_item_id)
    delete_paths = {
        str(item.get("path"))
        for item in (getattr(work, "path_intents", []) if work is not None else [])
        if isinstance(item, dict)
        and item.get("intent") == "delete"
        and isinstance(item.get("path"), str)
    }
    for artifact in evidence.artifacts:
        expected = "absent" if artifact in delete_paths else "present"
        if artifact_statuses.get(artifact) != expected:
            if expected == "present":
                errors.append(f"evidence {evidence.id} artifact is not present: {artifact}")
            else:
                errors.append(
                    f"evidence {evidence.id} artifact does not prove required deletion: "
                    f"{artifact}"
                )
    if receipt is not None:
        if not evidence.receipt_hash:
            errors.append(f"evidence {evidence.id} is not bound to receipt {receipt.id}")
        elif evidence.receipt_hash != receipt.receipt_hash:
            errors.append(f"evidence {evidence.id} receipt hash is stale")
        if (
            receipt.evidence_manifest_hash
            and receipt.evidence_manifest_hash != evidence.manifest_hash
        ):
            errors.append(f"receipt {receipt.id} points to a different evidence manifest")
    return errors


def _receipt_errors(receipt: Any) -> list[str]:
    if not receipt.receipt_hash:
        return [f"receipt {receipt.id} has no receipt hash"]
    record = {
        "id": receipt.id,
        "work_item_id": receipt.work_item_id,
        "attempt_id": receipt.attempt_id,
        "actor": receipt.actor,
        "context_packet": receipt.context_packet,
        "context_hash": receipt.context_hash,
        "sources_used": receipt.sources_used,
        "actions_taken": receipt.actions_taken,
        "outputs_created": receipt.outputs_created,
        "planned_external_writes": receipt.planned_external_writes,
        "queued_external_writes": receipt.queued_external_writes,
        "external_writes": receipt.external_writes,
        "not_done": receipt.not_done,
        "undo_refs": receipt.undo_refs,
        "previous_receipt_hash": receipt.previous_receipt_hash,
        "evidence_manifest_hash": receipt.evidence_manifest_hash,
        "timestamp": receipt.timestamp,
    }
    if receipt.receipt_hash != receipt_hash(record):
        return [f"receipt {receipt.id} hash verification failed"]
    return []


def _latest_for_attempt(records: list[Any], work_id: str, attempt_id: str) -> Any | None:
    return latest_for_work(
        [
            record
            for record in records
            if record.work_item_id == work_id and record.attempt_id == attempt_id
        ],
        work_id,
    )


def _attempt_head(attempt: Any) -> str:
    return attempt.head_sha or (attempt.commits[-1] if attempt.commits else "")


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{HASH_PREFIX}{hashlib.sha256(encoded).hexdigest()}"


def _record_value(record: Any, field: str, default: Any = "") -> Any:
    if isinstance(record, dict):
        return record.get(field, default)
    return getattr(record, field, default)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
