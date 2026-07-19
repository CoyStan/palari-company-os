from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .governance_journal import (
    JOURNAL_RELATIVE_PATH,
    V2_JOURNAL_RELATIVE_PATH,
    JournalVerificationContext,
)
from .path_policy import path_allowed, resolve_workspace_path
from .record_order import record_time_key
from .workspace import Workspace, WorkspaceError


HASH_PREFIX = "sha256:"
OUTPUT_BINDING_VERSION = "palari.evidence_outputs.v1"
GOVERNANCE_JOURNAL_RELATIVE_PATH = V2_JOURNAL_RELATIVE_PATH
LEGACY_GOVERNANCE_JOURNAL_RELATIVE_PATH = JOURNAL_RELATIVE_PATH


def git_artifact_state(
    workspace_path: Path,
    artifacts: list[str],
    *,
    governance_workspace_path: Path | None = None,
    path_intents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return the exact committed and tracked state used for proof binding."""

    try:
        root = workspace_path.expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return {"head_sha": "", "clean": False, "artifact_hashes": []}
    head_sha = _git_value(root, ["rev-parse", "HEAD"])
    dirty_paths = _tracked_dirty_paths(root)
    if dirty_paths is None:
        return {"head_sha": head_sha, "clean": False, "artifact_hashes": []}
    governance_root = governance_workspace_path or root
    governance_paths = _governance_projection_paths(root, governance_root)
    effective_path_intents = (
        path_intents
        if path_intents is not None
        else _unambiguous_workspace_path_intents(governance_root, artifacts)
    )
    return {
        "head_sha": head_sha,
        "clean": not (set(dirty_paths) - governance_paths),
        "artifact_hashes": artifact_hashes_at_root(
            root,
            artifacts,
            expected_absent_paths=_delete_intent_paths(effective_path_intents),
        ),
    }


def artifact_hashes_at_root(
    workspace_path: Path,
    artifacts: list[str],
    *,
    expected_absent_paths: set[str] | None = None,
) -> list[dict[str, str]]:
    """Hash bounded artifact bytes under one canonical repository root."""

    return _artifact_hashes(
        workspace_path,
        artifacts,
        expected_absent_paths=expected_absent_paths,
    )


def _tracked_dirty_paths(root: Path) -> list[str] | None:
    paths: set[str] = set()
    for arguments in (
        ("diff", "--no-ext-diff", "--no-renames", "--name-only", "-z", "--"),
        (
            "diff",
            "--cached",
            "--no-ext-diff",
            "--no-renames",
            "--name-only",
            "-z",
            "--",
        ),
    ):
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *arguments],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        try:
            paths.update(
                value for value in result.stdout.decode("utf-8").split("\0") if value
            )
        except UnicodeDecodeError:
            return None
    return sorted(paths)


def _governance_projection_paths(root: Path, workspace_path: Path) -> set[str]:
    data_path = workspace_path.expanduser().resolve()
    if data_path.is_dir():
        data_path /= "workspace.json"
    candidates = {
        data_path,
        data_path.parent / GOVERNANCE_JOURNAL_RELATIVE_PATH,
        data_path.parent / LEGACY_GOVERNANCE_JOURNAL_RELATIVE_PATH,
    }
    paths: set[str] = set()
    for candidate in candidates:
        try:
            paths.add(candidate.resolve().relative_to(root).as_posix())
        except ValueError:
            continue
    return paths


def stamp_evidence_record(
    record: dict[str, Any],
    workspace_path: Path,
    *,
    attempts: list[Any] | None = None,
    path_intents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    stamped = dict(record)
    if not stamped.get("output_binding_version"):
        stamped["output_binding_version"] = OUTPUT_BINDING_VERSION
    artifacts = _strings(stamped.get("artifacts", []))
    effective_path_intents = (
        path_intents
        if path_intents is not None
        else _workspace_work_path_intents(
            workspace_path,
            str(stamped.get("work_item_id") or ""),
        )
    )
    artifact_hashes = evidence_artifact_hashes(
        workspace_path,
        str(stamped.get("attempt_id") or ""),
        artifacts,
        attempts or [],
        expected_absent_paths=_delete_intent_paths(effective_path_intents),
    )
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
    if record.get("output_binding_version"):
        payload["output_binding_version"] = record["output_binding_version"]
    return _stable_hash(payload)


def receipt_hash(record: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in sorted(record.items())
        if key not in {"receipt_hash"} and value not in (None, "", [], {})
    }
    return _stable_hash(payload)


def stored_evidence_integrity_errors(
    evidence: Any,
    receipt: Any | None,
    *,
    path_intents: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    require_output_coverage: bool = True,
    require_version: bool = True,
) -> list[str]:
    """Verify stored exact-proof metadata without reading artifact bytes."""

    evidence_record = _plain_record(evidence)
    receipt_record = _plain_record(receipt) if receipt is not None else None
    evidence_id = str(evidence_record.get("id", ""))
    errors: list[str] = []
    if require_version and evidence_record.get("output_binding_version") != OUTPUT_BINDING_VERSION:
        errors.append(f"evidence {evidence_id} has no current output binding version")
    if (
        not evidence_record.get("manifest_hash")
        or evidence_record["manifest_hash"] != evidence_manifest_hash(evidence_record)
    ):
        errors.append(f"evidence {evidence_id} manifest content changed")
    if receipt_record is None:
        errors.append(f"evidence {evidence_id} receipt is missing")
    else:
        receipt_id = str(receipt_record.get("id", ""))
        declared_receipt_hash = str(receipt_record.get("receipt_hash", ""))
        if not declared_receipt_hash or declared_receipt_hash != receipt_hash(receipt_record):
            errors.append(f"receipt {receipt_id} content changed")
        if evidence_record.get("receipt_hash") != declared_receipt_hash:
            errors.append(f"evidence {evidence_id} receipt binding changed")

    artifacts = [str(path) for path in evidence_record.get("artifacts", [])]
    artifact_hashes = evidence_record.get("artifact_hashes", [])
    hash_records = [item for item in artifact_hashes if isinstance(item, dict)]
    hashes = {str(item.get("path", "")): item for item in hash_records}
    if len(hash_records) != len(artifact_hashes) or len(hashes) != len(hash_records):
        errors.append(f"evidence {evidence_id} output hashes contain duplicate or malformed paths")
    if set(hashes) != set(artifacts) or len(artifacts) != len(set(artifacts)):
        errors.append(f"evidence {evidence_id} output hashes are incomplete")

    delete_paths = {
        str(item.get("path", ""))
        for item in path_intents
        if isinstance(item, dict) and item.get("intent") == "delete"
    }
    for path, item in hashes.items():
        status = str(item.get("status", ""))
        digest = str(item.get("sha256", ""))
        if path in delete_paths:
            if status != "absent" or digest != f"{HASH_PREFIX}absent":
                errors.append(f"evidence {evidence_id} deletion proof is invalid for {path}")
        elif status != "present" or not _exact_sha256(digest):
            errors.append(f"evidence {evidence_id} artifact digest is invalid for {path}")

    outputs = (
        [str(path) for path in receipt_record.get("outputs_created", [])]
        if receipt_record is not None
        else []
    )
    if require_output_coverage:
        if not artifacts:
            errors.append(f"evidence {evidence_id} versioned output proof is vacuous")
        if not outputs or not set(outputs).issubset(artifacts):
            errors.append(f"evidence {evidence_id} receipt outputs are not artifact-hashed")
    return list(dict.fromkeys(errors))


def _plain_record(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    raise TypeError("stored evidence records must be mappings or dataclasses")


def _exact_sha256(value: str) -> bool:
    if not value.startswith(HASH_PREFIX):
        return False
    digest = value.removeprefix(HASH_PREFIX)
    return len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def verify_evidence(
    workspace: Workspace,
    evidence_id: str,
    *,
    require_output_coverage: bool | None = None,
    journal_context: JournalVerificationContext | None = None,
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
        "output_binding_version": getattr(evidence, "output_binding_version", ""),
        "receipt_hash": evidence.receipt_hash,
        "previous_receipt_hash": evidence.previous_receipt_hash,
        "summary": evidence.summary,
        "freshness": evidence.freshness,
        "timestamp": evidence.timestamp,
    }
    work_lookup = getattr(workspace, "work_item", None)
    work = work_lookup(evidence.work_item_id) if callable(work_lookup) else None
    path_intents = getattr(work, "path_intents", []) if work is not None else []
    expected_absent_paths = _delete_intent_paths(path_intents)
    recomputed_artifacts, exact_head_artifacts = _verification_artifact_hashes(
        workspace,
        evidence,
        expected_absent_paths=expected_absent_paths,
    )
    path_intent_verification = _verify_evidence_path_intents(
        workspace,
        evidence,
        path_intents,
    )
    recomputed_artifacts = _mark_invalid_path_intents(
        recomputed_artifacts,
        path_intent_verification,
    )
    recomputed_record = dict(record)
    recomputed_record["artifact_hashes"] = recomputed_artifacts
    recomputed_manifest = evidence_manifest_hash(recomputed_record)
    artifact_ok = (
        _sorted_artifact_hashes(evidence.artifact_hashes) == recomputed_artifacts
        and all(
            item.get("status")
            == ("absent" if item.get("path") in expected_absent_paths else "present")
            for item in recomputed_artifacts
        )
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
    output_coverage_ok = (
        bool(matching_receipts)
        and bool(declared_outputs)
        and bool(evidence.artifacts)
        and not unhashed_outputs
    )
    output_binding_version = str(getattr(evidence, "output_binding_version", "") or "")
    output_binding_version_ok = output_binding_version in {"", OUTPUT_BINDING_VERSION}
    coverage_required = (
        output_binding_version == OUTPUT_BINDING_VERSION
        if require_output_coverage is None
        else require_output_coverage
    )
    status_ok = evidence.status == "passed"
    journal_verification: dict[str, Any] | None = None
    journal_continuity_ok = True
    if exact_head_artifacts:
        if journal_context is None:
            from .governance_journal import verify_workspace_journal

            journal_verification = verify_workspace_journal(workspace.path)
        else:
            journal_verification = journal_context.verify(workspace.path)
        journal_continuity_ok = bool(journal_verification["ok"])
    ok = (
        status_ok
        and artifact_ok
        and manifest_ok
        and journal_continuity_ok
        and output_binding_version_ok
        and path_intent_verification["ok"]
        and (output_coverage_ok or not coverage_required)
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
        "exact_head_artifacts": exact_head_artifacts,
        "journal_continuity_ok": journal_continuity_ok,
        "journal_verification": journal_verification,
        "status_ok": status_ok,
        "path_intents_ok": path_intent_verification["ok"],
        "path_intent_verification": path_intent_verification,
        "base_ref_binding_ok": path_intent_verification["base_ref_binding_ok"],
        "output_binding_version": output_binding_version,
        "output_binding_version_ok": output_binding_version_ok,
        "output_coverage_ok": output_coverage_ok,
        "output_coverage_required": coverage_required,
        "declared_receipt_outputs": declared_outputs,
        "unhashed_receipt_outputs": unhashed_outputs,
        "receipt_checks": receipt_checks,
        "limitations": (
            []
            if coverage_required
            else ["legacy evidence does not claim complete receipt-output coverage"]
        ),
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

    A workspace file may live below the repository governed by an attempt. The
    recorded absolute root is used while it still contains the workspace. When
    proof moves to another linked worktree or clone, the current Git root is
    accepted only when it contains the exact recorded candidate commit. Every
    artifact must still stay inside the attempt's explicit allowed-path
    boundary. Legacy or incomplete attempts retain workspace-local behavior.
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
    if not allowed_paths and not forbidden_paths:
        return fallback
    if not root_value or not allowed_paths:
        raise ValueError("attempt artifact boundary requires workspace_path and allowed_paths")
    if any(not path_allowed(artifact, allowed_paths) for artifact in artifacts):
        raise ValueError("evidence artifact is outside attempt allowed_paths")
    if any(path_allowed(artifact, forbidden_paths) for artifact in artifacts):
        raise ValueError("evidence artifact is inside attempt forbidden_paths")

    candidate = Path(root_value).expanduser()
    if not candidate.is_absolute():
        raise ValueError("attempt workspace_path must be absolute for parent-root artifacts")
    try:
        candidate = candidate.resolve(strict=True)
        if not candidate.is_dir():
            raise ValueError("attempt workspace_path is not a directory")
        fallback.relative_to(candidate)
        return candidate
    except (OSError, RuntimeError, ValueError):
        return _relocated_git_artifact_root(fallback, attempt)


def _relocated_git_artifact_root(fallback: Path, attempt: Any) -> Path:
    current_root = _git_root(fallback)
    if current_root is None:
        raise ValueError(
            "workspace is not contained by attempt workspace_path and no portable Git root "
            "is available"
        )
    try:
        fallback.relative_to(current_root)
    except ValueError as exc:
        raise ValueError("workspace is not contained by its current Git root") from exc

    head_sha = str(_field(attempt, "head_sha") or "")
    if len(head_sha) != 40 or any(character not in "0123456789abcdef" for character in head_sha):
        raise ValueError("attempt candidate commit is required for portable artifact proof")
    resolved = _git_exact_object_value(
        current_root,
        ["rev-parse", "--verify", f"{head_sha}^{{commit}}"],
    )
    if resolved != head_sha:
        raise ValueError("attempt candidate commit is unavailable in the current Git repository")
    return current_root


def _git_root(path: Path) -> Path | None:
    value = _git_value(path, ["rev-parse", "--show-toplevel"])
    if not value:
        return None
    try:
        root = Path(value).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return root if root.is_dir() else None


def _git_value(path: Path, arguments: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_exact_object_value(path: Path, arguments: list[str]) -> str:
    """Read raw Git identity without allowing local replacement objects."""

    try:
        result = subprocess.run(
            ["git", "-C", str(path), "--no-replace-objects", *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def evidence_artifact_hashes(
    workspace_path: Path,
    attempt_id: str,
    artifacts: list[str],
    attempts: list[Any],
    *,
    expected_absent_paths: set[str] | None = None,
) -> list[dict[str, str]]:
    try:
        root = evidence_artifact_root(workspace_path, attempt_id, artifacts, attempts)
    except ValueError:
        return [
            {"path": artifact, "sha256": f"{HASH_PREFIX}unsafe", "status": "unsafe"}
            for artifact in sorted(artifacts)
        ]
    return _artifact_hashes(
        root,
        artifacts,
        expected_absent_paths=expected_absent_paths,
    )


def _verification_artifact_hashes(
    workspace: Workspace,
    evidence: Any,
    *,
    expected_absent_paths: set[str] | None = None,
) -> tuple[list[dict[str, str]], list[str]]:
    """Recompute proof bytes without creating a self-referential journal gate.

    Ordinary artifacts remain bound to current filesystem bytes. The workspace
    projection files that deterministically record proof creation are instead
    read from the evidence's exact Git commit; requiring their live bytes would
    make every successful proof append invalidate itself. Callers separately
    require the live journal to replay to the current workspace projection.
    """

    artifacts = list(evidence.artifacts)
    attempts = getattr(workspace, "attempts", [])
    try:
        root = evidence_artifact_root(
            workspace.path,
            evidence.attempt_id,
            artifacts,
            attempts,
        )
    except ValueError:
        return (
            [
                {"path": artifact, "sha256": f"{HASH_PREFIX}unsafe", "status": "unsafe"}
                for artifact in sorted(artifacts)
            ],
            [],
        )

    exact_head_artifacts = _governance_projection_artifacts(
        root,
        workspace.path,
        artifacts,
    )
    current_artifacts = [
        artifact for artifact in artifacts if artifact not in exact_head_artifacts
    ]
    hashes = _artifact_hashes(
        root,
        current_artifacts,
        expected_absent_paths=expected_absent_paths,
    )
    hashes.extend(
        _git_artifact_hashes_at_head(
            root,
            exact_head_artifacts,
            str(evidence.head_sha or ""),
            expected_absent_paths=expected_absent_paths,
        )
    )
    return sorted(hashes, key=lambda item: item["path"]), exact_head_artifacts


def _governance_projection_artifacts(
    artifact_root: Path,
    workspace_path: Path,
    artifacts: list[str],
) -> list[str]:
    data_path = Path(workspace_path).expanduser().resolve(strict=False)
    if data_path.is_dir():
        data_path /= "workspace.json"
    projection_paths = {
        data_path,
        *(
            path
            for path in (
                data_path.parent / GOVERNANCE_JOURNAL_RELATIVE_PATH,
                data_path.parent / LEGACY_GOVERNANCE_JOURNAL_RELATIVE_PATH,
            )
            if path.exists()
        ),
    }
    matches: list[str] = []
    for artifact in artifacts:
        try:
            artifact_path = resolve_workspace_path(artifact_root, artifact)
        except ValueError:
            continue
        if artifact_path in projection_paths:
            matches.append(artifact)
    return sorted(matches)


def _git_artifact_hashes_at_head(
    artifact_root: Path,
    artifacts: list[str],
    head_sha: str,
    *,
    expected_absent_paths: set[str] | None = None,
) -> list[dict[str, str]]:
    if not artifacts:
        return []
    git_root = _git_root(artifact_root)
    if (
        git_root is None
        or len(head_sha) != 40
        or any(character not in "0123456789abcdef" for character in head_sha)
        or _git_exact_object_value(
            git_root,
            ["rev-parse", "--verify", f"{head_sha}^{{commit}}"],
        )
        != head_sha
    ):
        return [
            {
                "path": artifact,
                "sha256": f"{HASH_PREFIX}unavailable",
                "status": "unavailable",
            }
            for artifact in sorted(artifacts)
        ]

    hashes: list[dict[str, str]] = []
    for artifact in artifacts:
        try:
            artifact_path = resolve_workspace_path(artifact_root, artifact)
            git_path = artifact_path.relative_to(git_root).as_posix()
        except ValueError:
            hashes.append(
                {"path": artifact, "sha256": f"{HASH_PREFIX}unsafe", "status": "unsafe"}
            )
            continue
        try:
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(git_root),
                    "--no-replace-objects",
                    "cat-file",
                    "blob",
                    f"{head_sha}:{git_path}",
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            result = None
        if result is None or result.returncode != 0:
            hashes.append(
                {
                    "path": artifact,
                    "sha256": (
                        f"{HASH_PREFIX}absent"
                        if artifact in (expected_absent_paths or set())
                        else f"{HASH_PREFIX}missing"
                    ),
                    "status": (
                        "absent"
                        if artifact in (expected_absent_paths or set())
                        else "missing"
                    ),
                }
            )
            continue
        digest = hashlib.sha256(result.stdout).hexdigest()
        hashes.append(
            {"path": artifact, "sha256": f"{HASH_PREFIX}{digest}", "status": "present"}
        )
    return sorted(hashes, key=lambda item: item["path"])


def _artifact_hashes(
    workspace_path: Path,
    artifacts: list[str],
    *,
    expected_absent_paths: set[str] | None = None,
) -> list[dict[str, str]]:
    hashes: list[dict[str, str]] = []
    expected_absent = expected_absent_paths or set()
    for artifact in artifacts:
        try:
            artifact_path = resolve_workspace_path(workspace_path, artifact)
        except ValueError:
            hashes.append({"path": artifact, "sha256": f"{HASH_PREFIX}unsafe", "status": "unsafe"})
            continue
        if not artifact_path.exists() and not artifact_path.is_symlink():
            if artifact in expected_absent:
                hashes.append(
                    {"path": artifact, "sha256": f"{HASH_PREFIX}absent", "status": "absent"}
                )
                continue
            hashes.append({"path": artifact, "sha256": f"{HASH_PREFIX}missing", "status": "missing"})
            continue
        if not artifact_path.is_file():
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


def _delete_intent_paths(value: Any) -> set[str]:
    if not isinstance(value, (list, tuple)):
        return set()
    return {
        str(item.get("path"))
        for item in value
        if isinstance(item, dict)
        and item.get("intent") == "delete"
        and isinstance(item.get("path"), str)
        and item.get("path")
    }


def _unambiguous_workspace_path_intents(
    workspace_path: Path,
    artifacts: list[str],
) -> list[dict[str, Any]]:
    """Recover CAS intent only when one workspace contract exactly owns the artifacts."""

    artifact_set = set(artifacts)
    if not artifact_set:
        return []
    try:
        workspace = Workspace.load(workspace_path)
    except (OSError, RuntimeError, WorkspaceError):
        return []
    candidates: list[list[dict[str, Any]]] = []
    for work in workspace.work_items:
        intents = [
            dict(item)
            for item in getattr(work, "path_intents", [])
            if isinstance(item, dict) and isinstance(item.get("path"), str)
        ]
        if intents and {str(item["path"]) for item in intents} == artifact_set:
            candidates.append(intents)
    return candidates[0] if len(candidates) == 1 else []


def _workspace_work_path_intents(
    workspace_path: Path,
    work_id: str,
) -> list[dict[str, Any]]:
    if not work_id:
        return []
    try:
        workspace = Workspace.load(workspace_path)
    except (OSError, RuntimeError, WorkspaceError):
        return []
    work = workspace.work_item(work_id)
    if work is None:
        return []
    return [
        dict(item)
        for item in getattr(work, "path_intents", [])
        if isinstance(item, dict)
    ]


def _verify_evidence_path_intents(
    workspace: Workspace,
    evidence: Any,
    raw_path_intents: Any,
) -> dict[str, Any]:
    """Verify exact path semantics from the attempt's immutable Git range.

    This is the authoritative check used when evidence is consumed.  It is
    deliberately independent of the command that produced the evidence, so a
    manual or alternate authoring path cannot bypass create/modify/delete
    semantics that were checked during agent advance.
    """

    path_intents: list[dict[str, str]] = []
    malformed = False
    if isinstance(raw_path_intents, (list, tuple)):
        for item in raw_path_intents:
            path = _field(item, "path")
            intent = _field(item, "intent")
            if (
                not isinstance(path, str)
                or not path.isprintable()
                or intent not in {"create", "modify", "delete"}
            ):
                malformed = True
                continue
            path_intents.append({"path": path, "intent": str(intent)})
    elif raw_path_intents not in (None, []):
        malformed = True

    attempts = [
        attempt
        for attempt in getattr(workspace, "attempts", [])
        if str(_field(attempt, "id") or "") == str(evidence.attempt_id or "")
        and str(_field(attempt, "work_item_id") or "")
        == str(evidence.work_item_id or "")
    ]
    attempt = attempts[0] if len(attempts) == 1 else None
    attempt_base = str(_field(attempt, "base_sha") or "") if attempt else ""
    binding_required = bool(path_intents) or bool(attempt_base)
    report: dict[str, Any] = {
        "required": bool(path_intents) or malformed,
        "ok": True,
        "attempt_id": str(evidence.attempt_id or ""),
        "base_ref_binding_required": binding_required,
        "base_ref_binding_ok": True,
        "head_binding_ok": True,
        "intents": path_intents,
        "checks": [],
        "errors": [],
        "invalid_paths": [],
    }
    if malformed:
        report["errors"].append(
            _path_intent_error(
                "PATH_INTENT_INVALID",
                "work path intents are malformed",
                "Repair the work contract before relying on its evidence.",
            )
        )
    if not binding_required:
        report["ok"] = not report["errors"]
        return report

    if attempt is None:
        report["base_ref_binding_ok"] = False
        report["head_binding_ok"] = False
        report["errors"].append(
            _path_intent_error(
                "EVIDENCE_ATTEMPT_MISSING",
                "evidence does not identify one associated attempt",
                "Record evidence against the exact work attempt and verify again.",
            )
        )
        return _finish_path_intent_report(report, path_intents)

    evidence_base = str(evidence.base_ref or "")
    if not attempt_base or evidence_base != attempt_base:
        report["base_ref_binding_ok"] = False
        report["errors"].append(
            _path_intent_error(
                "EVIDENCE_BASE_REF_MISMATCH",
                "evidence base_ref does not match the associated attempt base_sha",
                "Regenerate evidence from the exact attempt baseline.",
            )
        )

    attempt_head = str(_field(attempt, "head_sha") or "")
    evidence_head = str(evidence.head_sha or "")
    if attempt_head and evidence_head != attempt_head:
        report["head_binding_ok"] = False
        report["errors"].append(
            _path_intent_error(
                "EVIDENCE_HEAD_MISMATCH",
                "evidence head_sha does not match the associated attempt head_sha",
                "Regenerate evidence from the attempt's exact candidate commit.",
            )
        )

    if not path_intents:
        return _finish_path_intent_report(report, path_intents)

    try:
        root = evidence_artifact_root(
            workspace.path,
            str(evidence.attempt_id),
            list(evidence.artifacts),
            list(workspace.attempts),
        )
    except (ValueError, WorkspaceError) as exc:
        report["errors"].append(
            _path_intent_error(
                "PATH_INTENT_ROOT_UNSAFE",
                f"artifact root is unavailable or unsafe: {exc}",
                "Restore the bounded attempt workspace or exact candidate Git object.",
            )
        )
        return _finish_path_intent_report(report, path_intents)

    git_root, object_format, range_error = _exact_git_commit_range(
        root,
        attempt_base,
        evidence_head,
    )
    if range_error:
        code = (
            "PATH_INTENT_GIT_NON_ANCESTOR"
            if range_error == "non-ancestor"
            else "PATH_INTENT_GIT_UNREADABLE"
        )
        message = (
            "attempt base commit is not an ancestor of the evidence head commit"
            if range_error == "non-ancestor"
            else "attempt base and evidence head are not exact readable Git commits"
        )
        report["errors"].append(
            _path_intent_error(
                code,
                message,
                "Restore the exact commit ancestry and regenerate evidence.",
            )
        )
        return _finish_path_intent_report(report, path_intents)

    artifact_set = {
        artifact for artifact in evidence.artifacts if isinstance(artifact, str)
    }
    assert git_root is not None
    for item in path_intents:
        path = item["path"]
        intent = item["intent"]
        if path not in artifact_set:
            report["checks"].append(
                {"path": path, "intent": intent, "status": "invalid"}
            )
            report["errors"].append(
                _path_intent_error(
                    "PATH_INTENT_ARTIFACT_MISSING",
                    f"path intent {path} is absent from evidence artifacts",
                    "Include every exact path intent in the evidence manifest.",
                    path=path,
                )
            )
            continue
        transition = _git_path_intent_transition(
            root,
            git_root,
            path,
            intent,
            attempt_base,
            evidence_head,
            object_format,
        )
        if transition == "verified":
            report["checks"].append(
                {"path": path, "intent": intent, "status": "verified"}
            )
            continue
        report["checks"].append(
            {"path": path, "intent": intent, "status": "invalid"}
        )
        unreadable = transition == "unreadable"
        report["errors"].append(
            _path_intent_error(
                "PATH_INTENT_GIT_UNREADABLE" if unreadable else "PATH_INTENT_MISMATCH",
                (
                    f"Git tree state is unreadable for {path}"
                    if unreadable
                    else f"Git ancestry does not prove {intent} for {path}"
                ),
                (
                    "Restore the exact readable Git objects and verify again."
                    if unreadable
                    else "Make the declared mutation from the claimed base and regenerate evidence."
                ),
                path=path,
            )
        )
    return _finish_path_intent_report(report, path_intents)


def _finish_path_intent_report(
    report: dict[str, Any],
    path_intents: list[dict[str, str]],
) -> dict[str, Any]:
    checked = {str(item.get("path") or "") for item in report["checks"]}
    global_failure = bool(report["errors"]) and not report["checks"]
    invalid = {
        str(item.get("path") or "")
        for item in report["checks"]
        if item.get("status") != "verified"
    }
    if global_failure or not report["base_ref_binding_ok"] or not report["head_binding_ok"]:
        invalid.update(item["path"] for item in path_intents)
    if report["errors"] and checked != {item["path"] for item in path_intents}:
        invalid.update(item["path"] for item in path_intents if item["path"] not in checked)
    report["invalid_paths"] = sorted(invalid)
    report["ok"] = not report["errors"]
    return report


def _mark_invalid_path_intents(
    hashes: list[dict[str, Any]],
    verification: dict[str, Any],
) -> list[dict[str, Any]]:
    invalid_paths = set(verification.get("invalid_paths", []))
    if not invalid_paths:
        return hashes
    intents = {
        str(item.get("path") or ""): str(item.get("intent") or "")
        for item in verification.get("intents", [])
    }
    result: list[dict[str, Any]] = []
    for item in hashes:
        current = dict(item)
        path = str(current.get("path") or "")
        if path in invalid_paths:
            intent = intents.get(path)
            if not intent:
                intent = "path-intent"
            invalid_status = "invalid-deletion" if intent == "delete" else f"invalid-{intent}"
            current["sha256"] = f"{HASH_PREFIX}{invalid_status}"
            current["status"] = invalid_status
        result.append(current)
    return sorted(result, key=lambda value: str(value.get("path", "")))


def _path_intent_error(
    code: str,
    message: str,
    next_action: str,
    *,
    path: str = "",
) -> dict[str, str]:
    result = {"code": code, "message": message, "next_action": next_action}
    if path:
        result["path"] = path
    return result


def git_deletion_tombstone(
    root: Path,
    path: str,
    base_head: str,
    candidate_head: str,
) -> dict[str, str] | None:
    """Return exact Git ancestry for one regular-file deletion, or ``None``."""

    try:
        resolved_path = resolve_workspace_path(root, path)
    except ValueError:
        return None
    git_root, object_format, range_error = _exact_git_commit_range(
        root,
        base_head,
        candidate_head,
    )
    if git_root is None or range_error:
        return None
    try:
        git_path = resolved_path.relative_to(git_root).as_posix()
    except ValueError:
        return None
    previous_readable, previous = _git_tree_entry(git_root, base_head, git_path)
    current_readable, current = _git_tree_entry(git_root, candidate_head, git_path)
    if not previous_readable or not current_readable:
        return None
    if previous is None or current is not None:
        return None
    mode, object_type, oid = previous
    if object_type != "blob" or mode not in {"100644", "100755"}:
        return None
    expected_length = 40 if object_format == "sha1" else 64
    if len(oid) != expected_length or any(char not in "0123456789abcdef" for char in oid):
        return None
    return {
        "base_head": base_head,
        "git_object_format": object_format,
        "previous_git_oid": oid,
        "previous_git_mode": mode,
    }


def _exact_git_commit_range(
    root: Path,
    base_head: str,
    candidate_head: str,
) -> tuple[Path | None, str, str]:
    """Resolve two exact commits without replacements and prove ancestry."""

    git_root = _git_root(root)
    if git_root is None:
        return None, "", "unreadable"
    object_format = _git_exact_object_value(
        git_root,
        ["rev-parse", "--show-object-format"],
    )
    if object_format not in {"sha1", "sha256"}:
        return git_root, object_format, "unreadable"
    expected_length = 40 if object_format == "sha1" else 64
    for commit in (base_head, candidate_head):
        if len(commit) != expected_length or any(
            character not in "0123456789abcdef" for character in commit
        ):
            return git_root, object_format, "unreadable"
        resolved = _git_exact_object_value(
            git_root,
            ["rev-parse", "--verify", f"{commit}^{{commit}}"],
        )
        if resolved != commit:
            return git_root, object_format, "unreadable"
    ancestor = _git_is_ancestor(git_root, base_head, candidate_head)
    if ancestor is None:
        return git_root, object_format, "unreadable"
    if not ancestor:
        return git_root, object_format, "non-ancestor"
    return git_root, object_format, ""


def _git_is_ancestor(root: Path, base_head: str, candidate_head: str) -> bool | None:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "--no-replace-objects",
                "merge-base",
                "--is-ancestor",
                base_head,
                candidate_head,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def _git_path_intent_transition(
    artifact_root: Path,
    git_root: Path,
    path: str,
    intent: str,
    base_head: str,
    candidate_head: str,
    object_format: str,
) -> str:
    try:
        resolved_path = resolve_workspace_path(artifact_root, path)
        git_path = resolved_path.relative_to(git_root).as_posix()
    except ValueError:
        return "mismatch"
    previous_readable, previous = _git_tree_entry(git_root, base_head, git_path)
    current_readable, current = _git_tree_entry(git_root, candidate_head, git_path)
    if not previous_readable or not current_readable:
        return "unreadable"
    regular_previous = _regular_git_blob(previous, object_format)
    regular_current = _regular_git_blob(current, object_format)
    if intent == "create":
        satisfied = previous is None and regular_current
        return "verified" if satisfied else "mismatch"
    if intent == "modify":
        satisfied = (
            regular_previous
            and regular_current
            and previous is not None
            and current is not None
            and (previous[0], previous[2]) != (current[0], current[2])
        )
        return "verified" if satisfied else "mismatch"
    if intent == "delete":
        satisfied = regular_previous and current is None
        return "verified" if satisfied else "mismatch"
    return "mismatch"


def _regular_git_blob(entry: tuple[str, str, str] | None, object_format: str) -> bool:
    if entry is None:
        return False
    mode, object_type, oid = entry
    expected_length = 40 if object_format == "sha1" else 64
    return (
        object_type == "blob"
        and mode in {"100644", "100755"}
        and len(oid) == expected_length
        and all(character in "0123456789abcdef" for character in oid)
    )


def _git_tree_entry(
    root: Path,
    commit: str,
    path: str,
) -> tuple[bool, tuple[str, str, str] | None]:
    if not commit or not path:
        return False, None
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "--no-replace-objects",
                "ls-tree",
                "-z",
                commit,
                "--",
                path,
            ],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return False, None
    if result.returncode != 0:
        return False, None
    if not result.stdout:
        return True, None
    entries = [item for item in result.stdout.split(b"\0") if item]
    if len(entries) != 1 or b"\t" not in entries[0]:
        return False, None
    metadata, raw_path = entries[0].split(b"\t", 1)
    try:
        decoded_path = raw_path.decode("utf-8", "strict")
        parts = metadata.decode("ascii", "strict").split()
    except UnicodeDecodeError:
        return False, None
    if decoded_path != path:
        return False, None
    if len(parts) != 3:
        return False, None
    return True, (parts[0], parts[1], parts[2])


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
