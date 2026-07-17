from __future__ import annotations

from copy import deepcopy
from typing import Any

from .errors import WorkspaceError
from .pcaw_canonical import canonical_json_bytes, canonical_sha256
from .record_order import record_time_key
from .workspace import Workspace


PRESENTATION_SCHEMA_VERSION = "palari.approval-presentation.v1"
DECISION_SURFACE = "palari.human-decision-pack.v1"
DECISION_STATES = {
    "approved",
    "blocked",
    "deferred",
    "eligible",
    "executed",
    "non-batchable",
    "rejected",
    "stale",
}
APPROVABLE_STATES = {"approved", "eligible"}


def build_approval_presentation(
    workspace: Workspace,
    pack: dict[str, Any],
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    """Compile the exact layout-independent artifact offered for a pack decision."""

    decision_states = _evaluation_states(evaluation, pack)
    members: list[dict[str, Any]] = []
    for member in pack.get("members", []):
        projected = deepcopy(member)
        projected["decision_state"] = decision_states[str(member.get("id") or "")]
        projected["decision_context"] = _decision_context(workspace, member)
        members.append(projected)
    presentation = {
        "schema_version": PRESENTATION_SCHEMA_VERSION,
        "decision_surface": DECISION_SURFACE,
        "pack": {
            "pack_id": pack.get("pack_id", ""),
            "pack_digest": pack.get("pack_digest", ""),
        },
        "action": _action_context(pack, members),
        "summary": deepcopy(pack.get("cumulative_effect_summary", {})),
        "members": members,
        "external_effects": deepcopy(pack.get("external_effects", [])),
        "security_limitations": _security_limitations(),
    }
    validate_approval_presentation(presentation, pack)
    return presentation


def canonical_presentation_bytes(
    presentation: dict[str, Any],
    pack: dict[str, Any],
) -> bytes:
    validate_approval_presentation(presentation, pack)
    return canonical_json_bytes(presentation)


def approval_presentation_digest(
    presentation: dict[str, Any],
    pack: dict[str, Any],
) -> str:
    validate_approval_presentation(presentation, pack)
    return canonical_sha256(presentation)


def validate_approval_presentation(
    presentation: dict[str, Any],
    pack: dict[str, Any],
) -> None:
    expected = {
        "schema_version",
        "decision_surface",
        "pack",
        "action",
        "summary",
        "members",
        "external_effects",
        "security_limitations",
    }
    if not isinstance(presentation, dict) or set(presentation) != expected:
        raise WorkspaceError("approval presentation has unknown or missing fields")
    if presentation["schema_version"] != PRESENTATION_SCHEMA_VERSION:
        raise WorkspaceError("approval presentation schema version is unsupported")
    if presentation["decision_surface"] != DECISION_SURFACE:
        raise WorkspaceError("approval presentation decision surface is unsupported")
    if presentation["pack"] != {
        "pack_id": pack.get("pack_id"),
        "pack_digest": pack.get("pack_digest"),
    }:
        raise WorkspaceError("approval presentation is bound to a different pack")
    if presentation["summary"] != pack.get("cumulative_effect_summary"):
        raise WorkspaceError("approval presentation summary differs from its pack")
    if presentation["external_effects"] != pack.get("external_effects"):
        raise WorkspaceError("approval presentation external effects differ from its pack")
    if presentation["security_limitations"] != _security_limitations():
        raise WorkspaceError("approval presentation security limitations are stale")

    source_members = pack.get("members")
    presented_members = presentation["members"]
    if not isinstance(source_members, list) or not isinstance(presented_members, list):
        raise WorkspaceError("approval presentation members must be arrays")
    if len(source_members) != len(presented_members):
        raise WorkspaceError("approval presentation must cover every pack member exactly once")
    for source, presented in zip(source_members, presented_members, strict=True):
        if not isinstance(source, dict) or not isinstance(presented, dict):
            raise WorkspaceError("approval presentation member must be an object")
        context = presented.get("decision_context")
        decision_state = presented.get("decision_state")
        projected = deepcopy(presented)
        projected.pop("decision_context", None)
        projected.pop("decision_state", None)
        if projected != source:
            raise WorkspaceError("approval presentation member differs from its exact pack member")
        _validate_decision_context(context, str(source.get("id") or ""))
        _validate_decision_state(decision_state, str(source.get("id") or ""))
    if presentation["action"] != _action_context(pack, presented_members):
        raise WorkspaceError("approval presentation action context is stale or malformed")


def _evaluation_states(
    evaluation: dict[str, Any],
    pack: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    if not isinstance(evaluation, dict):
        raise WorkspaceError("approval presentation evaluation must be an object")
    if evaluation.get("pack_id") != pack.get("pack_id") or evaluation.get(
        "pack_digest"
    ) != pack.get("pack_digest"):
        raise WorkspaceError("approval presentation evaluation is bound to a different pack")
    evaluated_members = evaluation.get("members")
    if not isinstance(evaluated_members, list):
        raise WorkspaceError("approval presentation evaluation members must be an array")
    if [item.get("id") for item in evaluated_members if isinstance(item, dict)] != pack.get(
        "execution_order"
    ):
        raise WorkspaceError(
            "approval presentation evaluation must cover the exact execution order"
        )
    states: dict[str, dict[str, Any]] = {}
    for item in evaluated_members:
        if not isinstance(item, dict):
            raise WorkspaceError("approval presentation evaluation member must be an object")
        member_id = str(item.get("id") or "")
        state = {
            "state": item.get("state"),
            "reasons": deepcopy(item.get("reasons")),
            "next_safe_action": item.get("next_safe_action"),
        }
        _validate_decision_state(state, member_id)
        states[member_id] = state
    return states


def _action_context(
    pack: dict[str, Any],
    presented_members: list[dict[str, Any]],
) -> dict[str, Any]:
    states = [
        str(member.get("decision_state", {}).get("state") or "")
        for member in presented_members
        if isinstance(member, dict)
    ]
    approvable = any(state in APPROVABLE_STATES for state in states)
    decidable = any(state != "stale" for state in states)
    available: list[str] = []
    if approvable:
        available.extend(["approve", "approve-eligible"])
    if decidable:
        available.extend(["defer", "reject"])
    return {
        "available": available,
        "primary": "approve-eligible" if approvable else "inspect-exceptions",
        "execution_order": deepcopy(pack.get("execution_order", [])),
        "local_convergence": "atomic-when-authorized",
    }


def _validate_decision_state(value: Any, member_id: str) -> None:
    expected_fields = {"state", "reasons", "next_safe_action"}
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise WorkspaceError(
            f"approval presentation member {member_id} has malformed decision state"
        )
    if value["state"] not in DECISION_STATES:
        raise WorkspaceError(
            f"approval presentation member {member_id} has unsupported decision state"
        )
    reasons = value["reasons"]
    if not isinstance(reasons, list) or any(
        not isinstance(reason, str) or not reason for reason in reasons
    ):
        raise WorkspaceError(
            f"approval presentation member {member_id} decision reasons must be strings"
        )
    if not isinstance(value["next_safe_action"], str) or not value["next_safe_action"]:
        raise WorkspaceError(
            f"approval presentation member {member_id} lacks a next safe action"
        )


def _decision_context(workspace: Workspace, member: dict[str, Any]) -> list[dict[str, str]]:
    member_id = str(member.get("id") or "")
    proof = member.get("proof")
    reviewed_head = str(proof.get("reviewed_head") or "") if isinstance(proof, dict) else ""
    latest: dict[str, Any] = {}
    for decision in workspace.human_decisions:
        if decision.work_item_id != member_id or decision.reviewed_head != reviewed_head:
            continue
        previous = latest.get(decision.human_id)
        if previous is None or record_time_key(decision) > record_time_key(previous):
            latest[decision.human_id] = decision
    context: list[dict[str, str]] = []
    for human_id in sorted(latest):
        decision = latest[human_id]
        human = workspace.human(decision.human_id)
        context.append(
            {
                "id": decision.id,
                "human_id": decision.human_id,
                "human_availability": human.availability if human else "missing",
                "human_approval_capabilities": (
                    ",".join(sorted(human.approval_capabilities)) if human else ""
                ),
                "decision": decision.decision,
                "status": decision.status,
                "evidence_reference": decision.evidence_reference,
                "review_reference": decision.review_reference,
                "approval_pack_digest": decision.approval_pack_digest,
                "approval_presentation_digest": decision.approval_presentation_digest,
                "timestamp": decision.timestamp,
            }
        )
    return context


def _validate_decision_context(value: Any, member_id: str) -> None:
    if not isinstance(value, list):
        raise WorkspaceError(
            f"approval presentation member {member_id} decision_context must be an array"
        )
    expected_fields = {
        "id",
        "human_id",
        "human_availability",
        "human_approval_capabilities",
        "decision",
        "status",
        "evidence_reference",
        "review_reference",
        "approval_pack_digest",
        "approval_presentation_digest",
        "timestamp",
    }
    human_ids: list[str] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != expected_fields:
            raise WorkspaceError(
                f"approval presentation member {member_id} has malformed decision context"
            )
        if any(not isinstance(item[field], str) for field in expected_fields):
            raise WorkspaceError(
                f"approval presentation member {member_id} decision context must use strings"
            )
        if not item["id"] or not item["human_id"]:
            raise WorkspaceError(
                f"approval presentation member {member_id} decision context lacks identity"
            )
        human_ids.append(item["human_id"])
    if human_ids != sorted(human_ids) or len(human_ids) != len(set(human_ids)):
        raise WorkspaceError(
            f"approval presentation member {member_id} decision context is not canonical"
        )


def _security_limitations() -> list[str]:
    return [
        "The digest proves these canonical presentation-artifact bytes, not browser layout or font rendering.",
        "The bound decision surface records that these bytes were made available; compromised software could display different bytes.",
        "The binding does not prove that a person read, understood, or exercised sound judgment about the presentation.",
        "Actor attribution remains declared rather than cryptographically authenticated.",
    ]
