from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from .governance_kernel import evaluate_governance_case
from .pcaw_canonical import canonical_json_bytes, canonical_sha256
from .pcaw_protocol import build_pcaw_statement
from .pcaw_workspace import governance_case_from_workspace
from .workspace import Workspace, WorkspaceError


def export_pcaw_statement(
    workspace_path: Path | str,
    work_id: str,
    output_path: Path | str,
) -> dict[str, Any]:
    """Export a deterministic PCAW v1 statement, including incomplete work."""

    workspace = Workspace.load(workspace_path)
    governance_case, artifact_subjects = governance_case_from_workspace(workspace, work_id)
    absent_artifacts = sorted(
        item.path
        for item in (
            governance_case.evidence.artifact_hashes
            if governance_case.evidence is not None
            else ()
        )
        if item.status == "absent"
    )
    if absent_artifacts:
        raise WorkspaceError(
            "PCAW v1 proves present artifact bytes only; local deletion tombstones "
            "cannot be exported: " + ", ".join(absent_artifacts)
        )
    output = Path(output_path).expanduser().resolve()
    for item in artifact_subjects:
        artifact = (workspace.path / item["name"]).resolve()
        if artifact == output:
            raise WorkspaceError("proof output cannot overwrite one of its governed artifacts")

    statement = build_pcaw_statement(governance_case, artifact_subjects)
    payload = canonical_json_bytes(statement)
    _atomic_write(output, payload)
    evaluation = evaluate_governance_case(governance_case).to_dict()
    return {
        "schema_version": "pcaw.export.v1",
        "action": "export",
        "status": "exported",
        "proof_file": str(output),
        "work_id": work_id,
        "statement_digest": {
            "algorithm": "sha256",
            "value": canonical_sha256(statement).removeprefix("sha256:"),
        },
        "claimed_state": governance_case.claimed_state,
        "derived_lifecycle_state": evaluation.get("derived_state", ""),
        "artifact_subject_count": len(artifact_subjects),
        "security_limitations": list(statement["predicate"]["security_limitations"]),
    }


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = ""
    try:
        with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
            temporary = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary:
            Path(temporary).unlink(missing_ok=True)
