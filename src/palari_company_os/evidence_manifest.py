from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .path_policy import path_allowed, resolve_workspace_path
from .record_order import record_time_key
from .workspace import Workspace, WorkspaceError


HASH_PREFIX = "sha256:"


def stamp_evidence_record(record: dict[str, Any], workspace_path: Path) -> dict[str, Any]:
    stamped = dict(record)
    artifact_hashes = _artifact_hashes(workspace_path, _strings(stamped.get("artifacts", [])))
    stamped.setdefault("artifact_hashes", artifact_hashes)
    stamped["manifest_hash"] = evidence_manifest_hash(stamped)
    return stamped


def stamp_receipt_record(record: dict[str, Any], existing_receipts: list[dict[str, Any]]) -> dict[str, Any]:
    stamped = dict(record)
    previous = _previous_receipt_hash(stamped, existing_receipts)
    if previous and not stamped.get("previous_receipt_hash"):
        stamped["previous_receipt_hash"] = previous
    stamped["receipt_hash"] = receipt_hash(stamped)
    return stamped


def evidence_manifest_hash(record: dict[str, Any]) -> str:
    payload = {
        "id": record.get("id", ""),
        "work_item_id": record.get("work_item_id", ""),
        "attempt_id": record.get("attempt_id", ""),
        "head_sha": record.get("head_sha", ""),
        "status": record.get("status", ""),
        "base_ref": record.get("base_ref", ""),
        "commands": _strings(record.get("commands", [])),
        "artifacts": _strings(record.get("artifacts", [])),
        "artifact_hashes": _sorted_artifact_hashes(record.get("artifact_hashes", [])),
        "receipt_hash": record.get("receipt_hash", ""),
        "previous_receipt_hash": record.get("previous_receipt_hash", ""),
        "summary": record.get("summary", ""),
        "freshness": record.get("freshness", ""),
        "timestamp": record.get("timestamp", ""),
    }
    return _stable_hash(payload)


def receipt_hash(record: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in sorted(record.items())
        if key not in {"receipt_hash"} and value not in (None, "", [], {})
    }
    return _stable_hash(payload)


def verify_evidence(
    workspace: Workspace,
    evidence_id: str,
    *,
    require_output_coverage: bool = True,
) -> dict[str, Any]:
    evidence = next((item for item in workspace.evidence_runs if item.id == evidence_id), None)
    if evidence is None:
        known = ", ".join(sorted(item.id for item in workspace.evidence_runs))
        raise WorkspaceError(f"unknown evidence run {evidence_id}; known evidence runs: {known}")

    record = {
        "id": evidence.id,
        "work_item_id": evidence.work_item_id,
        "attempt_id": evidence.attempt_id,
        "head_sha": evidence.head_sha,
        "status": evidence.status,
        "base_ref": evidence.base_ref,
        "commands": evidence.commands,
        "artifacts": evidence.artifacts,
        "artifact_hashes": evidence.artifact_hashes,
        "receipt_hash": evidence.receipt_hash,
        "previous_receipt_hash": evidence.previous_receipt_hash,
        "summary": evidence.summary,
        "freshness": evidence.freshness,
        "timestamp": evidence.timestamp,
    }
    artifact_root = evidence_artifact_root(
        workspace.path,
        evidence.attempt_id,
        evidence.artifacts,
        getattr(workspace, "attempts", []),
    )
    recomputed_artifacts = _artifact_hashes(artifact_root, evidence.artifacts)
    recomputed_record = dict(record)
    recomputed_record["artifact_hashes"] = recomputed_artifacts
    recomputed_manifest = evidence_manifest_hash(recomputed_record)
    artifact_ok = (
        _sorted_artifact_hashes(evidence.artifact_hashes) == recomputed_artifacts
        and all(item.get("status") == "present" for item in recomputed_artifacts)
    )
    manifest_ok = bool(evidence.manifest_hash) and evidence.manifest_hash == recomputed_manifest
    receipt_checks = _receipt_checks(workspace, evidence)
    matching_receipts = _matching_receipts(workspace, evidence)
    declared_outputs = sorted(
        {
            output
            for receipt in matching_receipts
            for output in receipt.outputs_created
        }
    )
    unhashed_outputs = sorted(set(declared_outputs) - set(evidence.artifacts))
    output_coverage_ok = bool(matching_receipts) and not unhashed_outputs
    ok = (
        artifact_ok
        and manifest_ok
        and (output_coverage_ok or not require_output_coverage)
        and all(item["ok"] for item in receipt_checks)
    )
    return {
        "schema_version": "palari.evidence_verify.v1",
        "workspace": workspace.name,
        "evidence_id": evidence.id,
        "ok": ok,
        "artifact_hashes_ok": artifact_ok,
        "manifest_hash_ok": manifest_ok,
        "declared_manifest_hash": evidence.manifest_hash,
        "computed_manifest_hash": recomputed_manifest,
        "declared_artifact_hashes": _sorted_artifact_hashes(evidence.artifact_hashes),
        "computed_artifact_hashes": recomputed_artifacts,
        "output_coverage_ok": output_coverage_ok,
        "output_coverage_required": require_output_coverage,
        "declared_receipt_outputs": declared_outputs,
        "unhashed_receipt_outputs": unhashed_outputs,
        "receipt_checks": receipt_checks,
    }


def _receipt_checks(workspace: Workspace, evidence: Any) -> list[dict[str, Any]]:
    if not evidence.receipt_hash:
        return [
            {
                "receipt_id": "",
                "ok": False,
                "declared_receipt_hash": "",
                "computed_receipt_hash": "",
                "message": "evidence has no exact receipt hash",
            }
        ]

    matching = _matching_receipts(workspace, evidence)
    if not matching:
        return [
            {
                "receipt_id": "",
                "ok": False,
                "declared_receipt_hash": evidence.receipt_hash,
                "computed_receipt_hash": "",
                "message": "no receipt matches the evidence work, attempt, and receipt hash",
            }
        ]

    checks: list[dict[str, Any]] = []
    for receipt in matching:
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
        computed = receipt_hash(record)
        checks.append(
            {
                "receipt_id": receipt.id,
                "ok": not receipt.receipt_hash or receipt.receipt_hash == computed,
                "declared_receipt_hash": receipt.receipt_hash,
                "computed_receipt_hash": computed,
                "message": (
                    "receipt hash verified"
                    if receipt.receipt_hash == computed
                    else "receipt content does not match its declared hash"
                ),
            }
        )
    return checks


def _matching_receipts(workspace: Workspace, evidence: Any) -> list[Any]:
    return [
        receipt
        for receipt in workspace.receipts
        if receipt.work_item_id == evidence.work_item_id
        and receipt.attempt_id == evidence.attempt_id
        and receipt.receipt_hash == evidence.receipt_hash
    ]


def evidence_artifact_root(
    workspace_path: Path,
    attempt_id: str,
    artifacts: list[str],
    attempts: list[Any],
) -> Path:
    """Return the bounded root used to resolve an evidence artifact list.

    A workspace file may live below the repository governed by an attempt. In
    that case artifact paths can be resolved from the attempt's recorded
    workspace root only when the workspace itself is inside that root and every
    artifact is inside the attempt's explicit allowed-path boundary. Legacy or
    incomplete attempts retain the workspace-local behavior.
    """

    fallback = Path(workspace_path).expanduser().resolve()
    attempt = next(
        (item for item in attempts if str(_field(item, "id") or "") == attempt_id),
        None,
    )
    if attempt is None:
        return fallback

    root_value = str(_field(attempt, "workspace_path") or "")
    allowed_paths = _string_list(_field(attempt, "allowed_paths"))
    forbidden_paths = _string_list(_field(attempt, "forbidden_paths"))
    if not root_value or not allowed_paths:
        return fallback
    if any(not path_allowed(artifact, allowed_paths) for artifact in artifacts):
        return fallback
    if any(path_allowed(artifact, forbidden_paths) for artifact in artifacts):
        return fallback

    candidate = Path(root_value).expanduser()
    if not candidate.is_absolute():
        return fallback
    try:
        candidate = candidate.resolve(strict=True)
        if not candidate.is_dir():
            return fallback
        fallback.relative_to(candidate)
    except (OSError, RuntimeError, ValueError):
        return fallback
    return candidate


def _artifact_hashes(workspace_path: Path, artifacts: list[str]) -> list[dict[str, str]]:
    hashes: list[dict[str, str]] = []
    for artifact in artifacts:
        try:
            artifact_path = resolve_workspace_path(workspace_path, artifact)
        except ValueError:
            hashes.append({"path": artifact, "sha256": f"{HASH_PREFIX}unsafe", "status": "unsafe"})
            continue
        if not artifact_path.exists() or not artifact_path.is_file():
            hashes.append({"path": artifact, "sha256": f"{HASH_PREFIX}missing", "status": "missing"})
            continue
        try:
            digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        except OSError:
            hashes.append(
                {"path": artifact, "sha256": f"{HASH_PREFIX}unreadable", "status": "unreadable"}
            )
            continue
        hashes.append({"path": artifact, "sha256": f"{HASH_PREFIX}{digest}", "status": "present"})
    return sorted(hashes, key=lambda item: item["path"])


def _previous_receipt_hash(record: dict[str, Any], existing_receipts: list[dict[str, Any]]) -> str:
    work_item_id = record.get("work_item_id")
    candidates = [
        item
        for item in existing_receipts
        if item.get("work_item_id") == work_item_id and item.get("receipt_hash")
    ]
    if not candidates:
        return ""
    latest = max(candidates, key=record_time_key)
    return str(latest.get("receipt_hash", ""))


def _sorted_artifact_hashes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items = [dict(item) for item in value if isinstance(item, dict)]
    return sorted(items, key=lambda item: str(item.get("path", "")))


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _field(record: Any, name: str) -> Any:
    if isinstance(record, dict):
        return record.get(name)
    return getattr(record, name, None)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, str)]


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{HASH_PREFIX}{hashlib.sha256(encoded).hexdigest()}"
