from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import to_plain
from .workspace import Workspace, WorkspaceError


RISK_RANK = {"R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5}


@dataclass(frozen=True)
class AuthorityRule:
    id: str
    label: str
    mode: str
    summary: str
    require_human_for_risks: tuple[str, ...]
    receipt_ready_risks: tuple[str, ...]
    minimum_approval_count: int
    r5_approval_count: int
    allow_agent_scope_expansion: bool = False


BUILT_IN_PROFILES: tuple[AuthorityRule, ...] = (
    AuthorityRule(
        id="solo-founder",
        label="Solo Founder",
        mode="solo-founder",
        summary="Lightweight founder-operated mode. Low-risk receipt-ready work can close quickly.",
        require_human_for_risks=("R3", "R4", "R5"),
        receipt_ready_risks=("R1", "R2"),
        minimum_approval_count=1,
        r5_approval_count=1,
    ),
    AuthorityRule(
        id="team-safe",
        label="Team Safe",
        mode="team-safe",
        summary="Default team mode. R3+ work needs explicit qualified human approval.",
        require_human_for_risks=("R3", "R4", "R5"),
        receipt_ready_risks=("R1", "R2"),
        minimum_approval_count=1,
        r5_approval_count=2,
    ),
    AuthorityRule(
        id="strict",
        label="Strict",
        mode="strict",
        summary="High-assurance mode. Every risk tier requires human acceptance.",
        require_human_for_risks=("R1", "R2", "R3", "R4", "R5"),
        receipt_ready_risks=(),
        minimum_approval_count=1,
        r5_approval_count=2,
    ),
)


def authority_profiles(workspace: Workspace) -> dict[str, Any]:
    return {
        "schema_version": "palari.authority_profiles.v1",
        "workspace": workspace.name,
        "would_mutate": False,
        "profiles": [*_built_in_profiles(), *[to_plain(item) for item in workspace.authority_profiles]],
        "default_profile": "team-safe",
    }


def authority_check(
    workspace: Workspace,
    work_id: str,
    profile_id: str = "team-safe",
) -> dict[str, Any]:
    work = workspace.work_item(work_id)
    if work is None:
        known = ", ".join(sorted(item.id for item in workspace.work_items))
        raise WorkspaceError(f"unknown work item {work_id}; known work items: {known}")
    profile = _profile(workspace, profile_id)
    required_count = required_approval_count(work.risk, profile)
    requires_human = work.risk in set(profile["require_human_for_risks"])
    receipt_ready_allowed = work.risk in set(profile["receipt_ready_risks"])
    blockers: list[str] = []
    if work.required_approval_count < required_count:
        blockers.append(
            f"work requires {work.required_approval_count} approval(s), "
            f"profile requires {required_count}"
        )
    if requires_human and work.required_approval_count == 0:
        blockers.append(f"{profile['id']} requires human acceptance for {work.risk}")
    if work.risk == "R5" and work.required_approval_count < profile["r5_approval_count"]:
        blockers.append(f"R5 requires {profile['r5_approval_count']} approvals")
    return {
        "schema_version": "palari.authority_check.v1",
        "workspace": workspace.name,
        "profile": profile,
        "work_item": {
            "id": work.id,
            "title": work.title,
            "risk": work.risk,
            "required_approval_count": work.required_approval_count,
            "required_approval_capability": work.required_approval_capability,
        },
        "required_approval_count": required_count,
        "requires_human_acceptance": requires_human,
        "receipt_ready_allowed": receipt_ready_allowed,
        "agent_scope_expansion_allowed": bool(profile["allow_agent_scope_expansion"]),
        "ok": not blockers,
        "blockers": blockers,
        "next_action": _next_action(blockers, requires_human, required_count),
    }


def required_approval_count(risk: str, profile: dict[str, Any]) -> int:
    if risk == "R5":
        return int(profile["r5_approval_count"])
    if risk in set(profile["require_human_for_risks"]):
        return int(profile["minimum_approval_count"])
    return 0


def _profile(workspace: Workspace, profile_id: str) -> dict[str, Any]:
    built_ins = {profile.id: _profile_payload(profile) for profile in BUILT_IN_PROFILES}
    if profile_id in built_ins:
        return built_ins[profile_id]
    for profile in workspace.authority_profiles:
        if profile.id == profile_id:
            return to_plain(profile)
    known = ", ".join(sorted([*built_ins, *[profile.id for profile in workspace.authority_profiles]]))
    raise WorkspaceError(f"unknown authority profile {profile_id}; known profiles: {known}")


def _built_in_profiles() -> list[dict[str, Any]]:
    return [_profile_payload(profile) for profile in BUILT_IN_PROFILES]


def _profile_payload(profile: AuthorityRule) -> dict[str, Any]:
    return {
        "id": profile.id,
        "label": profile.label,
        "mode": profile.mode,
        "summary": profile.summary,
        "require_human_for_risks": list(profile.require_human_for_risks),
        "receipt_ready_risks": list(profile.receipt_ready_risks),
        "minimum_approval_count": profile.minimum_approval_count,
        "r5_approval_count": profile.r5_approval_count,
        "allow_agent_scope_expansion": profile.allow_agent_scope_expansion,
    }


def _next_action(blockers: list[str], requires_human: bool, required_count: int) -> str:
    if blockers:
        return "Raise the work approval requirement or lower the declared risk only with human review."
    if requires_human:
        return f"Collect {required_count} qualified human approval(s) before acceptance."
    return "Low-risk automation may proceed with receipt, evidence, and scope boundaries."
