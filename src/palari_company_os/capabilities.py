from __future__ import annotations

from typing import Any

from .models import to_plain
from .workspace import Workspace, WorkspaceError


def capability_catalog(workspace: Workspace) -> dict[str, Any]:
    capabilities = [_capability_record(item) for item in workspace.capabilities]
    capabilities.extend(_derived_capabilities(workspace))
    capabilities = _dedupe_by_id(capabilities)
    return {
        "schema_version": "palari.capabilities.v1",
        "workspace": workspace.name,
        "would_mutate": False,
        "capabilities": capabilities,
        "policy_boundary": _policy_boundary(),
    }


def capability_check(
    workspace: Workspace,
    work_id: str,
    palari_id: str = "",
) -> dict[str, Any]:
    work = workspace.work_item(work_id)
    if work is None:
        known = ", ".join(sorted(item.id for item in workspace.work_items))
        raise WorkspaceError(f"unknown work item {work_id}; known work items: {known}")
    palari_id = palari_id or work.palari
    catalog = capability_catalog(workspace)["capabilities"]
    allowed = [
        capability
        for capability in catalog
        if _capability_applies(capability, work, palari_id)
    ]
    blockers = [
        capability
        for capability in allowed
        if capability.get("status") != "enabled"
    ]
    return {
        "schema_version": "palari.capability_check.v1",
        "workspace": workspace.name,
        "work_item": {
            "id": work.id,
            "title": work.title,
            "risk": work.risk,
            "palari": work.palari,
        },
        "palari": palari_id,
        "ok": len(blockers) == 0,
        "allowed_capabilities": allowed,
        "blockers": blockers,
        "policy_boundary": _policy_boundary(),
    }


def export_policy(
    workspace: Workspace,
    work_id: str,
    palari_id: str = "",
) -> dict[str, Any]:
    check = capability_check(workspace, work_id, palari_id)
    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"unknown work item {work_id}")
    return {
        "schema_version": "palari.capability_policy.v1",
        "workspace": workspace.name,
        "work_item_id": work.id,
        "palari": check["palari"],
        "capabilities": check["allowed_capabilities"],
        "filesystem": {
            "read": list(work.allowed_resources),
            "write": list(work.output_targets or work.allowed_resources),
            "forbidden_actions": list(work.forbidden_actions),
        },
        "external_actions": {
            "allowed": list(work.allowed_actions),
            "requires_approval": True,
        },
        "enforcement": {
            "agents_may_accept_work": False,
            "agents_may_expand_scope": False,
            "completion_requires_palari_acceptance_gate": True,
            "evidence_and_receipts_required": True,
        },
    }


def allowed_capabilities_for_packet(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
) -> list[dict[str, Any]]:
    return capability_check(workspace, work_id, palari_id)["allowed_capabilities"]


def _capability_record(item: Any) -> dict[str, Any]:
    payload = to_plain(item)
    payload["derived"] = False
    return payload


def _derived_capabilities(workspace: Workspace) -> list[dict[str, Any]]:
    capabilities: list[dict[str, Any]] = []
    if any(work.allowed_resources or work.output_targets for work in workspace.work_items):
        capabilities.append(
            {
                "id": "repo-code",
                "label": "Repository Code",
                "kind": "repo",
                "provider": "local",
                "status": "enabled",
                "allowed_actions": ["read", "write"],
                "allowed_palaris": [],
                "source_ids": [],
                "risk_level": "standard",
                "policy_ref": "palari.capability_policy.v1",
                "notes": "Derived from work item allowed_resources and output_targets.",
                "derived": True,
            }
        )
    for integration in workspace.integrations:
        capabilities.append(
            {
                "id": f"integration-{integration.id}",
                "label": integration.label,
                "kind": "integration",
                "provider": integration.provider,
                "status": "enabled" if integration.enabled else "disabled",
                "allowed_actions": integration.allowed_actions,
                "allowed_palaris": [],
                "source_ids": integration.source_ids,
                "risk_level": integration.risk_level,
                "policy_ref": "palari.integration_outbox_check.v1",
                "notes": "Derived from integration declaration; live calls remain disabled.",
                "derived": True,
            }
        )
    for source in workspace.playbook_sources:
        capabilities.append(
            {
                "id": f"playbook-source-{source.id}",
                "label": source.label,
                "kind": "skill_pack",
                "provider": source.provider or "playbook",
                "status": "enabled" if source.enabled else "disabled",
                "allowed_actions": ["recommend"],
                "allowed_palaris": [],
                "source_ids": [],
                "risk_level": "low",
                "policy_ref": source.uri,
                "notes": "Derived from external playbook source.",
                "derived": True,
            }
        )
    return capabilities


def _capability_applies(capability: dict[str, Any], work: Any, palari_id: str) -> bool:
    allowed_palaris = capability.get("allowed_palaris", [])
    if allowed_palaris and palari_id not in allowed_palaris:
        return False
    kind = capability.get("kind", "")
    if kind == "repo":
        return bool(work.allowed_resources or work.output_targets)
    if kind == "integration":
        return bool(set(work.allowed_actions) & set(capability.get("allowed_actions", [])))
    if kind in {"skill_pack", "playbook"}:
        return bool(work.recommended_playbooks)
    if kind in {"external_tool", "mcp_adapter", "policy"}:
        return bool(set(work.allowed_actions) & set(capability.get("allowed_actions", [])))
    return False


def _dedupe_by_id(capabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for capability in capabilities:
        by_id.setdefault(str(capability.get("id", "")), capability)
    return [by_id[key] for key in sorted(by_id)]


def _policy_boundary() -> dict[str, Any]:
    return {
        "acceptance_owner": "Palari Company OS",
        "adapter_rule": "Adapters may execute only inside declared capability policy.",
        "must_not": [
            "No adapter may record human acceptance.",
            "No adapter may expand scope without an open decision.",
            "No adapter may bypass evidence, receipt, review, or authority gates.",
        ],
    }
