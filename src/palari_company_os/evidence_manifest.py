from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .governance_journal import JournalVerificationContext
from .path_policy import path_allowed, resolve_workspace_path
from .record_order import record_time_key
from .workspace import Workspace, WorkspaceError


HASH_PREFIX = "sha256:"
OUTPUT_BINDING_VERSION = "palari.evidence_outputs.v1"
GOVERNANCE_HISTORY_RELATIVE_PATH = ".palari/history.jsonl"
GOVERNANCE_JOURNAL_RELATIVE_PATH = ".palari/governance-journal.v1.jsonl"


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
        data_path.parent / ".palari" / "history.jsonl",
        data_path.parent / ".palari" / "governance-journal.v1.jsonl",
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
    expected_absent_paths = _delete_intent_paths(
        getattr(work, "path_intents", []) if work is not None else []
    )
    recomputed_artifacts, exact_head_artifacts = _verification_artifact_hashes(
        workspace,
        evidence,
        expected_absent_paths=expected_absent_paths,
    )
    recomputed_artifacts = _enforce_verified_deletions(
        workspace,
        evidence,
        recomputed_artifacts,
        expected_absent_paths,
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
    except (OSError, subprocess.SubprocessError):
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
    except (OSError, subprocess.SubprocessError):
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
    journal_path = data_path.parent / GOVERNANCE_JOURNAL_RELATIVE_PATH
    if not journal_path.exists():
        return []
    projection_paths = {
        data_path,
        data_path.parent / GOVERNANCE_HISTORY_RELATIVE_PATH,
        journal_path,
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


def _enforce_verified_deletions(
    workspace: Workspace,
    evidence: Any,
    hashes: list[dict[str, Any]],
    delete_paths: set[str],
) -> list[dict[str, Any]]:
    """Accept absence only when Git proves a regular file was deleted.

    The evidence record stays compatible with the existing atomic authoring
    path by persisting only the core ``absent`` marker.  Verification derives
    the stronger ancestry fact from the immutable base and candidate commits.
    A missing base blob, unsupported object format, non-file entry, or path
    that reappears at the candidate head changes the recomputed value so exact
    artifact and manifest comparison fail closed.
    """

    if not delete_paths:
        return hashes
    try:
        root = evidence_artifact_root(
            workspace.path,
            str(evidence.attempt_id),
            list(evidence.artifacts),
            list(workspace.attempts),
        )
    except (ValueError, WorkspaceError):
        unavailable = [
            (
                {
                    **item,
                    "sha256": f"{HASH_PREFIX}invalid-deletion",
                    "status": "invalid-deletion",
                }
                if str(item.get("path") or "") in delete_paths
                else dict(item)
            )
            for item in hashes
        ]
        return sorted(unavailable, key=lambda value: str(value.get("path", "")))
    result: list[dict[str, Any]] = []
    for item in hashes:
        current = dict(item)
        path = str(current.get("path") or "")
        if path in delete_paths and current.get("status") == "absent":
            tombstone = git_deletion_tombstone(
                root,
                path,
                str(evidence.base_ref or ""),
                str(evidence.head_sha or ""),
            )
            if tombstone is None:
                current["sha256"] = f"{HASH_PREFIX}invalid-deletion"
                current["status"] = "invalid-deletion"
        result.append(current)
    return sorted(result, key=lambda value: str(value.get("path", "")))


def git_deletion_tombstone(
    root: Path,
    path: str,
    base_head: str,
    candidate_head: str,
) -> dict[str, str] | None:
    """Return exact Git ancestry for one regular-file deletion, or ``None``."""

    try:
        resolve_workspace_path(root, path)
    except ValueError:
        return None
    object_format = _git_value(root, ["rev-parse", "--show-object-format"])
    if object_format not in {"sha1", "sha256"}:
        return None
    expected_length = 40 if object_format == "sha1" else 64
    if any(
        len(commit) != expected_length
        or any(char not in "0123456789abcdef" for char in commit)
        for commit in (base_head, candidate_head)
    ):
        return None
    previous = _git_tree_entry(root, base_head, path)
    current = _git_tree_entry(root, candidate_head, path)
    if previous is None or current is not None:
        return None
    mode, object_type, oid = previous
    if object_type != "blob" or mode not in {"100644", "100755"}:
        return None
    if len(oid) != expected_length or any(char not in "0123456789abcdef" for char in oid):
        return None
    return {
        "base_head": base_head,
        "git_object_format": object_format,
        "previous_git_oid": oid,
        "previous_git_mode": mode,
    }


def _git_tree_entry(root: Path, commit: str, path: str) -> tuple[str, str, str] | None:
    if not commit or not path:
        return None
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
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    entries = [item for item in result.stdout.split(b"\0") if item]
    if len(entries) != 1 or b"\t" not in entries[0]:
        return None
    metadata, raw_path = entries[0].split(b"\t", 1)
    if raw_path.decode("utf-8", "surrogateescape") != path:
        return None
    parts = metadata.decode("ascii", "strict").split()
    if len(parts) != 3:
        return None
    return parts[0], parts[1], parts[2]


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
