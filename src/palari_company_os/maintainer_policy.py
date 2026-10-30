from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .errors import WorkspaceError
from .path_policy import validate_workspace_path
from .verification_attestations import current_verification_binding_error
from .workspace import current_attempt_for_work, latest_for_work
from .workspace_layout import (
    MAINTAINER_STATE_ROOT,
    MAINTAINER_WORKSPACE_FILENAME,
    is_maintainer_workspace,
)


MAINTAINER_LOCAL_ACTIONS = frozenset({"local_write"})


@dataclass(frozen=True)
class MaintainerPolicyViolation:
    code: str
    message: str
    missing: str


def normalized_action(value: str) -> str:
    """Normalize a capability label without treating punctuation as authority."""

    parts: list[str] = []
    current: list[str] = []
    for character in value.lower():
        if character.isalnum():
            current.append(character)
        elif current:
            parts.append("".join(current))
            current = []
    if current:
        parts.append("".join(current))
    return "_".join(parts)


def unsupported_maintainer_actions(actions: Iterable[str]) -> list[str]:
    """Return every non-empty capability outside Maintainer Profile v1."""

    declared = [str(value).strip() for value in actions if str(value).strip()]
    return sorted(
        {
            action
            for action in declared
            if normalized_action(action) not in MAINTAINER_LOCAL_ACTIONS
        }
    )


def maintainer_current_proof_error(workspace: Any, work: Any) -> str:
    """Return why current Maintainer proof cannot be reviewed or approved."""

    if not is_maintainer_workspace(getattr(workspace, "data_path")):
        return ""
    attempt = current_attempt_for_work(work, getattr(workspace, "attempts"))
    evidence = latest_for_work(getattr(workspace, "evidence_runs"), work.id)
    if attempt is None or evidence is None:
        return ""
    proof_head = attempt.head_sha or (
        attempt.commits[-1] if attempt.commits else ""
    )
    if evidence.attempt_id != attempt.id or evidence.head_sha != proof_head:
        return (
            "The current Maintainer evidence is not bound to the active exact "
            "attempt and Git head."
        )
    binding_error = current_verification_binding_error(
        workspace,
        work,
        maintainer=True,
    )
    if binding_error:
        return binding_error
    from .authoring import _assert_reconciliation_git_state

    try:
        _assert_reconciliation_git_state(
            str(attempt.workspace_path),
            str(workspace.data_path),
            list(evidence.artifacts),
            proof_head,
            list(evidence.artifact_hashes),
        )
    except WorkspaceError as exc:
        return (
            "The reviewed Maintainer source candidate is no longer current: "
            + str(exc)
        )
    return ""


def maintainer_profile_violations(
    workspace: Any,
    work: Any,
) -> list[MaintainerPolicyViolation]:
    """Evaluate every authoritative Maintainer Profile v1 boundary."""

    data_path = getattr(workspace, "data_path")
    if not is_maintainer_workspace(data_path):
        return []
    work_id = str(getattr(work, "id"))
    violations: list[MaintainerPolicyViolation] = []
    denied_actions = unsupported_maintainer_actions(
        getattr(work, "allowed_actions", [])
    )
    receipts = [
        receipt
        for receipt in getattr(workspace, "receipts")
        if receipt.work_item_id == work_id
    ]
    external_state = bool(
        any(
            item.work_item_id == work_id
            for item in getattr(workspace, "integration_plans")
        )
        or any(
            item.work_item_id == work_id
            for item in getattr(workspace, "integration_outbox")
        )
        or any(
            (
                receipt.planned_external_writes
                or receipt.queued_external_writes
                or receipt.external_writes
            )
            for receipt in receipts
        )
    )
    sensitive_sources: list[str] = []
    for source_id in getattr(work, "allowed_sources", []):
        source = getattr(workspace, "source")(source_id)
        if source is None:
            continue
        descriptor = " ".join(
            str(getattr(source, field, "") or "").lower()
            for field in (
                "label",
                "kind",
                "provider",
                "uri",
                "access_mode",
                "data_class",
            )
        )
        if (
            str(source.data_class).lower() in {"confidential", "restricted"}
            or bool(source.redaction_required)
            or any(
                marker in descriptor
                for marker in ("secret", "credential", "password", "token")
            )
        ):
            sensitive_sources.append(str(source.id))
    if denied_actions or external_state or sensitive_sources:
        detail: list[str] = []
        if denied_actions:
            detail.append("actions " + ", ".join(denied_actions))
        if external_state:
            detail.append("planned, queued, or recorded external state")
        if sensitive_sources:
            detail.append(
                "sensitive sources " + ", ".join(sorted(sensitive_sources))
            )
        violations.append(
            MaintainerPolicyViolation(
                "MAINTAINER_PROFILE_CAPABILITY_DENIED",
                "Maintainer Profile v1 permits reversible local source work "
                "only; "
                + "; ".join(detail)
                + ".",
                "a local-only task contract",
            )
        )

    declared_paths = [
        str(value)
        for value in (
            list(getattr(work, "allowed_resources", []))
            + list(getattr(work, "output_targets", []))
            + [
                item.get("path", "")
                for item in getattr(work, "path_intents", [])
                if isinstance(item, dict)
            ]
        )
        if isinstance(value, str)
    ]
    write_paths = [
        str(value)
        for value in (
            list(getattr(work, "output_targets", []))
            + [
                item.get("path", "")
                for item in getattr(work, "path_intents", [])
                if isinstance(item, dict)
            ]
        )
        if isinstance(value, str)
    ]
    protected = {
        MAINTAINER_WORKSPACE_FILENAME,
        MAINTAINER_STATE_ROOT,
        ".git",
    }
    normalized_declared: list[tuple[str, str]] = []
    unsafe: set[str] = set()
    for path in declared_paths:
        try:
            normalized = validate_workspace_path(path)
        except ValueError:
            unsafe.add(path)
            continue
        normalized_declared.append((path, normalized))
        if normalized != path:
            unsafe.add(path)
    normalized_writes: list[tuple[str, str]] = []
    for path in write_paths:
        try:
            normalized_writes.append((path, validate_workspace_path(path)))
        except ValueError:
            continue
    overlaps = sorted(
        unsafe
        | {
            raw
            for raw, path in normalized_declared
            if any(
                path == root or path.startswith(root + "/")
                for root in protected
            )
        }
        | {
            raw
            for raw, path in normalized_writes
            if path == "workspace.json"
            or path == ".palari"
            or path.startswith(".palari/")
        }
    )
    if overlaps:
        violations.append(
            MaintainerPolicyViolation(
                "MAINTAINER_PROFILE_STATE_PATH_DENIED",
                "Maintainer tasks cannot declare profile state or Git metadata "
                "as task output: "
                + ", ".join(overlaps),
                "source-only task paths",
            )
        )

    if int(getattr(work, "required_approval_count", 0)) < 1:
        violations.append(
            MaintainerPolicyViolation(
                "MAINTAINER_PROFILE_EVIDENCE_FLOOR",
                "Maintainer Profile v1 requires the complete verification "
                "profile, independent review, and one human approval even for "
                "local R1 work.",
                "at least one required human approval",
            )
        )
    return violations
