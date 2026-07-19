from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .governance_kernel import (
    EXTERNAL_WRITE_ACTIONS,
    TERMINAL_WORK_STATUSES,
    low_risk_completion_policy_applies,
)
from .read_models import detail
from .repo_docs import documentation_state, recommended_docs_for_work
from .review_guides import build_review_guide
from .workspace import Workspace


SUPPORTED_MODES = {"execute", "review"}


def build_agent_brief(
    workspace: Workspace,
    work_id: str,
    palari_id: str,
    mode: str,
) -> dict[str, Any]:
    mode = mode or "execute"
    created_at = _timestamp()
    work = workspace.work_item(work_id)
    palari = workspace.palari(palari_id)
    docs_state = documentation_state(workspace.path)
    packet: dict[str, Any] = {
        "schema_version": "palari.agent_packet.v1",
        "packet_id": _packet_id(work_id, palari_id, mode),
        "created_at": created_at,
        "mode": mode,
        "workspace": workspace.name,
        "status": "blocked",
        "agent": _palari_ref(palari_id, palari),
        "work_item": _work_ref(work_id, work),
        "documentation_state": docs_state,
        "recommended_docs": [],
        "blockers": [],
        "next_allowed_commands": [],
        "omitted_context": [_omitted_context(workspace), _omitted_doc_context(docs_state)],
    }

    blockers = _initial_blockers(mode, work_id, work, palari_id, palari)
    if work is None or palari is None or mode not in SUPPORTED_MODES:
        return _finalize_packet(packet, blockers)

    work_detail = detail(workspace, work.id)
    review_context = (
        _review_context(workspace, work.id, mode)
        if mode == "review"
        and work_detail["attention"] == "needs-review"
        else None
    )
    blockers.extend(
        _work_blockers(workspace, work_detail, palari_id, mode, review_context)
    )
    status = "blocked" if blockers else "ready"
    proof_state = _proof_state(work_detail)
    capability_policy = _capability_policy(workspace, work.id, palari_id)

    packet.update(
        {
            "status": status,
            "agent": _palari_ref(palari_id, palari),
            "work_item": _work_packet(work_detail["work_item"]),
            "goal": _goal_packet(work_detail["goal"]),
            "workbench": _workbench_packet(work_detail["workbench"]),
            "dependencies": [_dependency_packet(item) for item in work_detail["dependencies"]],
            "one_sentence_instruction": _instruction(
                work_detail, status, mode, palari.name
            ),
            "allowed_paths": _allowed_paths(work_detail["work_item"], mode),
            "allowed_resources": list(work.allowed_resources),
            "allowed_capabilities": capability_policy["allowed_capabilities"],
            "capability_policy": capability_policy["policy_boundary"],
            "allowed_sources": [_source_packet(item) for item in work_detail["sources"]],
            "forbidden_actions": _forbidden_actions(work_detail),
            "required_output": _required_output(work_detail["work_item"], mode),
            "completion_contract": _completion_contract(work_detail, mode),
            "stop_conditions": _stop_conditions(work_detail, status, mode),
            "state": _state_packet(work_detail),
            "proof_state": proof_state,
            "documentation_state": docs_state,
            "recommended_docs": recommended_docs_for_work(work_detail, workspace.path),
            "next_allowed_commands": _next_allowed_commands(
                work.id,
                palari_id,
                status,
                mode,
                review_context,
            ),
            "blockers": blockers,
        }
    )
    if review_context:
        packet["review_context"] = review_context
        if review_context["human_review_commands"]:
            packet["human_action_boundary"] = _human_action_boundary()
        matching_agent_commands = [
            item
            for item in review_context["agent_review_commands"]
            if item.get("reviewer") == palari_id
        ]
        if matching_agent_commands:
            packet["agent_action_boundary"] = _agent_action_boundary(
                matching_agent_commands
            )
    return _finalize_packet(packet, blockers)


def _initial_blockers(
    mode: str,
    work_id: str,
    work: Any,
    palari_id: str,
    palari: Any,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if mode not in SUPPORTED_MODES:
        blockers.append(
            _blocker(
                "UNSUPPORTED_MODE",
                f"Agent packet mode {mode!r} is not supported in v1.",
                missing="supported mode",
            )
        )
    if palari is None:
        blockers.append(
            _blocker(
                "MISSING_PALARI",
                f"Palari not found: {palari_id}",
                missing="declared Palari",
            )
        )
    if work is None:
        blockers.append(
            _blocker(
                "MISSING_WORK_ITEM",
                f"Work item not found: {work_id}",
                missing="declared work item",
            )
        )
    return blockers


def _work_blockers(
    workspace: Workspace,
    work_detail: dict[str, Any],
    palari_id: str,
    mode: str,
    review_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    work = work_detail["work_item"]
    workbench = work_detail["workbench"]
    assigned = work.get("palari") == palari_id
    allowed_by_workbench = bool(workbench and palari_id in workbench.get("palari_ids", []))
    reviewer_ids = {
        candidate.get("id")
        for candidate in (review_context or {}).get("reviewer_candidates", [])
        if candidate.get("identity_type") == "palari"
    }
    assigned_for_mode = (
        palari_id in reviewer_ids if mode == "review" else assigned or allowed_by_workbench
    )
    if not assigned_for_mode:
        missing = (
            "eligible independent Palari reviewer"
            if mode == "review"
            else "assigned or workbench-allowed Palari"
        )
        blockers.append(
            _blocker(
                "PALARI_NOT_ASSIGNED",
                f"{palari_id} is not authorized for {mode} mode on {work['id']}.",
                missing=missing,
            )
        )

    if mode == "execute":
        for dependency in work_detail["dependencies"]:
            if dependency.get("status") not in TERMINAL_WORK_STATUSES:
                blockers.append(
                    _blocker(
                        "DEPENDENCY_NOT_TERMINAL",
                        f"Dependency {dependency['id']} is {dependency.get('status', 'unknown')}.",
                        missing="terminal dependency",
                    )
                )

    source_ids = {source["id"] for source in work_detail["sources"]}
    for source_id in work.get("allowed_sources", []):
        if source_id not in source_ids:
            blockers.append(
                _blocker(
                    "SOURCE_MISSING",
                    f"Allowed source {source_id} is not available in packet sources.",
                    missing="declared source",
                )
            )
    for source in work_detail["sources"]:
        allowed_palaris = source.get("allowed_palaris", [])
        if allowed_palaris and palari_id not in allowed_palaris:
            blockers.append(
                _blocker(
                    "SOURCE_NOT_ALLOWED",
                    f"Source {source['id']} is not allowed for {palari_id}.",
                    missing="source permission",
                )
            )

    if mode == "execute":
        external_actions = sorted(set(work.get("allowed_actions", [])) & EXTERNAL_WRITE_ACTIONS)
        has_approved_plan = any(
            plan.get("status") == "approved" for plan in work_detail["integration_plans"]
        )
        has_queued_outbox = any(
            item.get("status") == "queued" for item in work_detail["integration_outbox"]
        )
        if external_actions and not (has_approved_plan or has_queued_outbox):
            blockers.append(
                _blocker(
                    "EXTERNAL_WRITE_REQUIRES_APPROVAL",
                    "This work allows an external write, but no approved integration plan or queued outbox item exists.",
                    missing="approved integration plan",
                )
            )

    attention = work_detail["attention"]
    if mode == "review":
        if attention == "needs-review":
            if work_detail.get("evidence") is None:
                blockers.append(
                    _blocker(
                        "REVIEW_CONTEXT_MISSING",
                        "Review mode needs current evidence to inspect.",
                        missing="reviewable evidence",
                    )
                )
            return blockers
        if attention == "needs-human-decision":
            blockers.append(
                _blocker(
                    "HUMAN_DECISION_REQUIRED",
                    work_detail["why"],
                    missing="human decision",
                )
            )
            return blockers
        if attention == "closed":
            blockers.append(_blocker("WORK_CLOSED", work_detail["why"], missing="open work item"))
            return blockers
        blockers.append(
            _blocker(
                "REVIEW_NOT_READY",
                "The work is not ready for independent review; current exact evidence is required first.",
                missing="review-ready work",
            )
        )
        return blockers

    if attention == "needs-human-decision":
        blockers.append(
            _blocker(
                "HUMAN_DECISION_REQUIRED",
                work_detail["why"],
                missing="human decision",
            )
        )
    elif attention == "blocked":
        blockers.append(_blocker("WORK_BLOCKED", work_detail["why"], missing="unblocked work"))
    elif attention == "closed":
        blockers.append(_blocker("WORK_CLOSED", work_detail["why"], missing="open work item"))
    elif attention == "ready-to-complete":
        blockers.append(
            _blocker(
                "TERMINALIZATION_PENDING",
                work_detail["why"],
                missing="deterministic terminal reconciliation",
            )
        )
    elif attention == "ready-to-integrate":
        blockers.append(
            _blocker(
                "INTEGRATION_BOUNDARY",
                work_detail["why"],
                missing="human integration action",
            )
        )
    elif attention == "needs-review":
        blockers.append(
            _blocker(
                "REVIEW_REQUIRED",
                work_detail["why"],
                missing="review-mode packet",
            )
        )
    return blockers


def _finalize_packet(packet: dict[str, Any], blockers: list[dict[str, Any]]) -> dict[str, Any]:
    packet["blockers"] = blockers
    packet["status"] = "blocked" if blockers else packet.get("status", "ready")
    packet["context_hash"] = _context_hash(packet)
    return packet


def _palari_ref(palari_id: str, palari: Any) -> dict[str, Any]:
    if palari is None:
        return {"id": palari_id, "found": False}
    return _palari_packet(
        {
            "id": palari.id,
            "name": palari.name,
            "role": palari.role,
            "scope": palari.scope,
            "default_worker": palari.default_worker,
            "forbidden_actions": palari.forbidden_actions,
            "standards": palari.standards,
        },
        palari_id,
    )


def _palari_packet(record: dict[str, Any] | None, palari_id: str) -> dict[str, Any]:
    if record is None:
        return {"id": palari_id, "found": False}
    return {
        "id": record["id"],
        "name": record.get("name", record["id"]),
        "role": record.get("role", ""),
        "scope": record.get("scope", ""),
        "default_worker": record.get("default_worker", ""),
        "standards": record.get("standards", []),
        "forbidden_actions": record.get("forbidden_actions", []),
        "found": True,
    }


def _work_ref(work_id: str, work: Any) -> dict[str, Any]:
    if work is None:
        return {"id": work_id, "found": False}
    return _work_packet(
        {
            "id": work.id,
            "title": work.title,
            "risk": work.risk,
            "status": work.status,
            "scope": work.scope,
            "acceptance_target": work.acceptance_target,
        }
    )


def _work_packet(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "title": record.get("title", ""),
        "risk": record.get("risk", ""),
        "status": record.get("status", ""),
        "intensity": record.get("intensity", ""),
        "objective": record.get("scope", ""),
        "acceptance_target": record.get("acceptance_target", ""),
        "required_approval_count": record.get("required_approval_count", 0),
        "required_approval_capability": record.get("required_approval_capability", ""),
        "found": True,
    }


def _goal_packet(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "id": record["id"],
        "title": record.get("title", ""),
        "status": record.get("status", ""),
        "priority": record.get("priority", ""),
        "owner": record.get("owner", ""),
        "success_criteria": record.get("success_criteria", []),
    }


def _workbench_packet(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "id": record["id"],
        "label": record.get("label", ""),
        "summary": record.get("summary", ""),
        "status": record.get("status", ""),
    }


def _dependency_packet(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "title": record.get("title", ""),
        "status": record.get("status", ""),
        "risk": record.get("risk", ""),
    }


def _source_packet(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "label": record.get("label", ""),
        "kind": record.get("kind", ""),
        "provider": record.get("provider", ""),
        "access_mode": record.get("access_mode", ""),
        "selected": record.get("selected", False),
        "owner_human": record.get("owner_human", ""),
        "allowed_palaris": record.get("allowed_palaris", []),
        "data_class": record.get("data_class", ""),
        "authority": record.get("authority", ""),
        "steward_human": record.get("steward_human", ""),
        "freshness_sla": record.get("freshness_sla", ""),
        "redaction_required": record.get("redaction_required", False),
        "last_seen_revision": record.get("last_seen_revision", ""),
        "last_read_at": record.get("last_read_at", ""),
    }


def _instruction(
    work_detail: dict[str, Any], status: str, mode: str, acting_palari_name: str
) -> str:
    work = work_detail["work_item"]
    palari = work_detail["palari"] or {"name": work.get("palari", "Palari")}
    if status == "blocked":
        return f"Do not execute {work['id']} yet; resolve the packet blockers first."
    objective = work.get("scope") or work.get("title", "")
    if mode == "review":
        return (
            f"{acting_palari_name} should independently review "
            f"{work['id']} against its scope, evidence, receipt, and forbidden actions."
        )
    return (
        f"{palari.get('name', work.get('palari', 'Palari'))} should work on "
        f"{work['id']}: {objective}"
    )


def _allowed_paths(work: dict[str, Any], mode: str) -> dict[str, list[str]]:
    if mode == "review":
        return {
            "read": list(work.get("allowed_resources", [])),
            "write": [],
        }
    path_intents = _path_intents(work)
    return {
        "read": list(work.get("allowed_resources", [])),
        "write": (
            [item["path"] for item in path_intents]
            if path_intents
            else list(work.get("output_targets", []) or work.get("allowed_resources", []))
        ),
    }


def _forbidden_actions(work_detail: dict[str, Any]) -> list[str]:
    work_actions = work_detail["work_item"].get("forbidden_actions", [])
    palari_actions = (work_detail["palari"] or {}).get("forbidden_actions", [])
    return sorted(set(work_actions + palari_actions))


def _required_output(work: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode == "review":
        return {
            "review_summary": "State whether the work matches scope, evidence, receipt, and safety boundaries.",
            "suggested_verdicts": [
                "accept-ready",
                "changes-requested",
                "needs-human-decision",
                "blocked",
            ],
            "must_not": [
                "edit work outputs",
                "record a human review without explicit human instruction",
                "record a Palari review under any identity other than the packet actor",
                "convert an advisory review into human acceptance",
                "perform external writes",
            ],
        }
    path_intents = _path_intents(work)
    required = {
        "output_targets": (
            [item["path"] for item in path_intents if item["intent"] != "delete"]
            if path_intents
            else list(work.get("output_targets", []))
        ),
        "fallback_write_paths": list(work.get("allowed_resources", [])),
        "acceptance_target": work.get("acceptance_target", ""),
        "verification_expectations": list(work.get("verification_expectations", [])),
        "must_not": list(work.get("forbidden_actions", [])),
    }
    if path_intents:
        required["path_intents"] = path_intents
    return required


def _path_intents(work: dict[str, Any]) -> list[dict[str, str]]:
    value = work.get("path_intents", [])
    if not isinstance(value, list):
        return []
    return [
        {"path": str(item["path"]), "intent": str(item["intent"])}
        for item in value
        if isinstance(item, dict)
        and isinstance(item.get("path"), str)
        and item.get("path")
        and item.get("intent") in {"create", "modify", "delete"}
    ]


def _completion_contract(work_detail: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode == "review":
        return {
            "requires_receipt": False,
            "requires_evidence": True,
            "requires_review": False,
            "requires_human_decision": False,
            "external_writes_allowed": False,
            "external_write_actions": [],
            "review_mode": True,
        }
    work = work_detail["work_item"]
    external_actions = sorted(set(work.get("allowed_actions", [])) & EXTERNAL_WRITE_ACTIONS)
    receipt = work_detail.get("receipt") or {}
    low_risk_light = low_risk_completion_policy_applies(
        risk=str(work.get("risk", "")),
        intensity=str(work.get("intensity", "")),
        required_approval_count=int(work.get("required_approval_count", 0)),
        allowed_actions=list(work.get("allowed_actions", [])),
        external_writes=list(receipt.get("external_writes", [])),
        planned_external_writes=list(receipt.get("planned_external_writes", [])),
        queued_external_writes=list(receipt.get("queued_external_writes", [])),
    )
    return {
        "requires_receipt": True,
        "requires_evidence": True,
        "requires_review": not low_risk_light,
        "requires_human_decision": not low_risk_light,
        "external_writes_allowed": bool(external_actions),
        "external_write_actions": external_actions,
    }


def _stop_conditions(work_detail: dict[str, Any], status: str, mode: str) -> list[str]:
    conditions = [
        "Stop if you need to read or write outside allowed_paths.",
        "Stop if you need a source not listed in allowed_sources.",
        "Stop if you need an external write without an approved integration plan.",
        "Stop if a human decision, approval, or clarification is required.",
        "Stop if the work objective is ambiguous after reading this packet.",
    ]
    if mode == "review":
        conditions.insert(0, "Stop before editing work outputs; review mode is read-only.")
        conditions.append("Stop if the review requires human authority beyond a recommendation.")
    if status == "blocked":
        conditions.insert(0, "Stop because this packet is blocked.")
    if work_detail["work_item"].get("forbidden_actions"):
        conditions.append("Stop before doing any forbidden action listed in this packet.")
    return conditions


def _state_packet(work_detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "attention": work_detail["attention"],
        "why": work_detail["why"],
        "next_action": work_detail["next_action"],
        "next_step_type": work_detail["next_step_type"],
        "safety": work_detail["safety"],
        "active_parallel_attempts": work_detail["active_parallel_attempts"],
        "coordination_warnings": work_detail["coordination_warnings"],
    }


def _proof_state(work_detail: dict[str, Any]) -> dict[str, Any]:
    return {
        "attempt": _attempt_ref(work_detail["attempt"]),
        "receipt": _record_ref(
            work_detail["receipt"],
            [
                "id",
                "attempt_id",
                "outputs_created",
                "planned_external_writes",
                "queued_external_writes",
                "external_writes",
                "context_packet",
                "context_hash",
                "receipt_hash",
                "previous_receipt_hash",
                "evidence_manifest_hash",
                "timestamp",
            ],
        ),
        "evidence": _record_ref(
            work_detail["evidence"],
            ["id", "status", "head_sha", "manifest_hash", "timestamp"],
        ),
        "review": _record_ref(work_detail["review"], ["id", "verdict", "reviewed_head", "timestamp"]),
        "human_decision": _record_ref(
            work_detail["human_decision"],
            ["id", "human_id", "decision", "status", "timestamp"],
        ),
        "integration": {
            "state": work_detail["safety"]["integration_state"],
            "plans": [
                _record_ref(item, ["id", "integration_id", "event", "action", "status"])
                for item in work_detail["integration_plans"]
            ],
            "outbox": [
                _record_ref(item, ["id", "plan_id", "event", "action", "status"])
                for item in work_detail["integration_outbox"]
            ],
        },
    }


def _attempt_ref(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    payload = {
        field: record.get(field, "")
        for field in (
            "id",
            "status",
            "actor",
            "branch",
            "workspace_path",
            "base_sha",
            "head_sha",
            "changed_files",
            "allowed_paths",
            "forbidden_paths",
            "claim_id",
            "claim_expires_at",
        )
        if field in record
    }
    commits = record.get("commits", [])
    if not payload.get("head_sha") and isinstance(commits, list) and commits:
        payload["head_sha"] = str(commits[-1])
    return payload


def _record_ref(record: dict[str, Any] | None, fields: list[str]) -> dict[str, Any] | None:
    if record is None:
        return None
    return {field: record.get(field, "") for field in fields if field in record}


def _next_allowed_commands(
    work_id: str,
    palari_id: str,
    status: str,
    mode: str,
    review_context: dict[str, Any] | None = None,
) -> list[str]:
    if status == "blocked":
        return [
            f"palari detail {work_id} --json",
            "palari queue --json",
            "palari validate --json",
        ]
    if mode == "review":
        commands = [
            f"palari review guide {work_id} --json",
            f"palari detail {work_id} --json",
            "palari validate --json",
        ]
        commands.extend(
            item["command"]
            for item in (review_context or {}).get("agent_review_commands", [])
            if item.get("reviewer") == palari_id
        )
        return commands
    return [
        f"palari scope {work_id} --json",
        f"palari detail {work_id} --json",
        "palari validate --json",
        f"palari agent advance {work_id} --as {palari_id} --json",
    ]


def _review_context(workspace: Workspace, work_id: str, mode: str) -> dict[str, Any] | None:
    if mode != "review":
        return None
    guide = build_review_guide(workspace, work_id)
    commands = guide.get("review_record_commands", [])
    return {
        "command": f"palari review guide {work_id} --json",
        "status": guide.get("status", ""),
        "attention": guide.get("attention", ""),
        "why": guide.get("why", ""),
        "attempt": guide.get("attempt", {}),
        "evidence": guide.get("evidence", {}),
        "receipt": guide.get("receipt", {}),
        "review_focus": guide.get("review_focus", []),
        "reviewer_candidates": guide.get("reviewer_candidates", []),
        "suggested_verdicts": guide.get("suggested_verdicts", []),
        "review_record_commands": guide.get("review_record_commands", []),
        "agent_review_commands": [
            item for item in commands if item.get("identity_type") == "palari"
        ],
        "human_review_commands": [
            item for item in commands if item.get("identity_type") == "human"
        ],
    }


def _human_action_boundary() -> dict[str, Any]:
    return {
        "agent_may_execute": False,
        "agent_allowed_use": "Quote or summarize human-only commands for a human supervisor.",
        "human_only_command_fields": [
            "review_context.human_review_commands[].command",
        ],
        "must_not": [
            "Do not run human review record commands.",
            "Do not claim to be the human reviewer.",
            "Do not convert a review recommendation into human acceptance.",
        ],
    }


def _agent_action_boundary(commands: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "agent_may_execute": True,
        "agent_action_command_fields": [
            "review_context.agent_review_commands[].command",
        ],
        "count": len(commands),
        "must": [
            "Execute only the command whose reviewer matches this packet actor.",
            "Keep the verdict advisory; it never records human acceptance.",
        ],
        "must_not": [
            "Do not record a verdict for the builder identity.",
            "Do not run any human review or human-decision command.",
        ],
    }


def _capability_policy(workspace: Workspace, work_id: str, palari_id: str) -> dict[str, Any]:
    from .capabilities import capability_check

    return capability_check(workspace, work_id, palari_id)


def _blocker(code: str, message: str, *, missing: str = "") -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "missing": missing,
        "human_visible": True,
    }


def _omitted_context(workspace: Workspace) -> dict[str, Any]:
    return {
        "kind": "workspace_records",
        "reason": "Agent packet v1 includes only records directly related to the selected work item.",
        "counts": {
            "goals": len(workspace.goals),
            "work_items": len(workspace.work_items),
            "palaris": len(workspace.palaris),
            "sources": len(workspace.sources),
        },
    }


def _omitted_doc_context(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "agent_ready_docs",
        "reason": "Agent packet v1 points to relevant docs but does not include full documentation text.",
        "documentation_status": state.get("status", "unknown"),
        "recommended_next_command": state.get("recommended_next_command", ""),
    }


def _packet_id(work_id: str, palari_id: str, mode: str) -> str:
    return f"PACKET-{_safe_id(work_id)}-{_safe_id(palari_id)}-{_safe_id(mode).upper()}-V1"


def _safe_id(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)
    return cleaned.strip("-") or "UNKNOWN"


def _context_hash(packet: dict[str, Any]) -> str:
    stable = {key: value for key, value in packet.items() if key not in {"created_at", "context_hash"}}
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
