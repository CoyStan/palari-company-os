from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from .errors import WorkspaceError
from .history import append_history_event
from .models import Human, Integration, IntegrationPlan, WorkItem, to_plain
from .store import load_store, validate_data, write_store
from .workspace import Workspace


PROVIDER_ACTIONS = {
    "slack": {"notify"},
    "github": {"notify", "comment", "create_issue"},
    "jira": {"notify", "comment", "create_issue", "update_issue"},
    "email": {"notify"},
}


def list_integrations(workspace: Workspace) -> dict[str, Any]:
    return {
        "workspace": workspace.name,
        "integrations": [_integration_summary(integration) for integration in workspace.integrations],
    }


def check_integration(workspace: Workspace, integration_id: str) -> dict[str, Any]:
    integration = _integration_or_raise(workspace, integration_id)
    supported_actions = sorted(PROVIDER_ACTIONS.get(integration.provider, set()))
    allowed_actions = sorted(set(integration.allowed_actions) & set(supported_actions))
    blocked_actions = sorted(set(integration.allowed_actions) - set(supported_actions))
    return {
        "workspace": workspace.name,
        "integration": to_plain(integration),
        "valid": True,
        "enabled": integration.enabled,
        "dry_run_only": True,
        "provider_supported_actions": supported_actions,
        "plannable_actions": allowed_actions,
        "blocked_actions": blocked_actions,
        "secret_ref_present": bool(integration.secret_ref),
        "notes": [
            "No live provider calls are available in this slice.",
            "secret_ref is metadata only; Palari does not read secrets for checks.",
        ],
    }


def plan_integration(
    workspace: Workspace,
    integration_id: str,
    work_id: str,
    event: str,
    action: str,
) -> dict[str, Any]:
    integration = _integration_or_raise(workspace, integration_id)
    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work item not found: {work_id}")
    _assert_can_plan(integration, event, action)
    payload = _payload_preview(workspace, integration, work, event, action)
    return {
        "workspace": workspace.name,
        "dry_run": True,
        "would_call_provider": False,
        "recorded": False,
        "integration_plan": None,
        "integration": _integration_summary(integration),
        "work_item": {
            "id": work.id,
            "title": work.title,
            "risk": work.risk,
            "status": work.status,
        },
        "event": event,
        "action": action,
        "payload_preview": payload,
        "safety": {
            "live_side_effects": "disabled",
            "secret_handling": "secret_ref only; no secret value read",
            "source_boundary": _source_boundary(workspace, integration, work),
        },
        "next_action": "Review the dry-run payload before enabling any future live connector.",
    }


def record_integration_plan(
    workspace_path: str,
    integration_id: str,
    work_id: str,
    event: str,
    action: str,
    *,
    actor: str = "",
    plan_id: str = "",
) -> dict[str, Any]:
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    preview = plan_integration(workspace, integration_id, work_id, event, action)
    integration = _integration_or_raise(workspace, integration_id)
    work = workspace.work_item(work_id)
    if work is None:
        raise WorkspaceError(f"work item not found: {work_id}")

    record = _plan_record(preview, integration, work, actor=actor, plan_id=plan_id)
    records = store.data.setdefault("integration_plans", [])
    if not isinstance(records, list):
        raise WorkspaceError("integration_plans must be a list of objects")
    if any(isinstance(item, dict) and item.get("id") == record["id"] for item in records):
        raise WorkspaceError(f"integration plan already exists: {record['id']}")
    records.append(record)
    workspace = write_store(store)
    history_event = append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command="integration plan",
        action="planned",
        object_type="integration-plan",
        object_collection="integration_plans",
        object_id=str(record["id"]),
        actor=str(record["actor"]),
        before=None,
        after=record,
    )
    refreshed = plan_integration(workspace, integration_id, work_id, event, action)
    refreshed["recorded"] = True
    refreshed["integration_plan"] = record
    refreshed["history_event"] = history_event
    return refreshed


def decide_integration_plan(
    workspace_path: str,
    plan_id: str,
    human_id: str,
    decision: str,
    *,
    reason: str = "",
) -> dict[str, Any]:
    target_status = {
        "approve": "approved",
        "reject": "rejected",
        "cancel": "canceled",
    }.get(decision)
    if target_status is None:
        raise WorkspaceError(f"unsupported integration plan decision: {decision}")
    reason = reason.strip()
    if target_status in {"rejected", "canceled"} and not reason:
        raise WorkspaceError(f"integration plan {decision} requires a reason")

    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    plan = workspace.integration_plan(plan_id)
    if plan is None:
        known = ", ".join(sorted(item.id for item in workspace.integration_plans))
        raise WorkspaceError(f"integration plan not found: {plan_id}; known plans: {known}")
    if plan.status != "pending-approval":
        raise WorkspaceError(
            f"integration plan {plan_id} cannot transition from {plan.status}; "
            "only pending-approval plans can be decided"
        )
    human = workspace.human(human_id)
    if human is None:
        known = ", ".join(sorted(item.id for item in workspace.humans))
        raise WorkspaceError(f"human not found: {human_id}; known humans: {known}")
    integration = _integration_or_raise(workspace, plan.integration_id)
    work = workspace.work_item(plan.work_item_id)
    if work is None:
        raise WorkspaceError(f"work item not found: {plan.work_item_id}")
    _assert_human_can_decide_plan(human, work, integration, plan)

    records = store.data.get("integration_plans")
    if not isinstance(records, list):
        raise WorkspaceError("integration_plans must be a list of objects")
    record = next(
        (item for item in records if isinstance(item, dict) and item.get("id") == plan_id),
        None,
    )
    if record is None:
        raise WorkspaceError(f"integration plan record not found: {plan_id}")
    before = deepcopy(record)
    now = _timestamp()
    record.update(
        {
            "status": target_status,
            "reviewed_by": human.id,
            "reviewed_at": now,
            "decision_reason": reason,
        }
    )

    workspace = write_store(store)
    after_plan = workspace.integration_plan(plan_id)
    after = to_plain(after_plan) if after_plan is not None else deepcopy(record)
    history_event = append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command=f"integration {decision}",
        action=target_status,
        object_type="integration-plan",
        object_collection="integration_plans",
        object_id=plan_id,
        actor=human.id,
        before=before,
        after=after,
    )
    return {
        "workspace": workspace.name,
        "dry_run": True,
        "would_call_provider": False,
        "decision": decision,
        "status": target_status,
        "integration_plan": after,
        "human": {
            "id": human.id,
            "name": human.name,
            "authority_level": human.authority_level,
            "approval_capabilities": human.approval_capabilities,
        },
        "history_event": history_event,
        "next_action": _decision_next_action(target_status),
    }


def enqueue_integration_plan(
    workspace_path: str,
    plan_id: str,
    human_id: str,
) -> dict[str, Any]:
    store = load_store(workspace_path)
    workspace = validate_data(store.data_path, store.data)
    plan = workspace.integration_plan(plan_id)
    if plan is None:
        known = ", ".join(sorted(item.id for item in workspace.integration_plans))
        raise WorkspaceError(f"integration plan not found: {plan_id}; known plans: {known}")
    if plan.status != "approved":
        raise WorkspaceError(
            f"integration plan {plan_id} must be approved before enqueue; status is {plan.status}"
        )
    human = workspace.human(human_id)
    if human is None:
        known = ", ".join(sorted(item.id for item in workspace.humans))
        raise WorkspaceError(f"human not found: {human_id}; known humans: {known}")
    integration = _integration_or_raise(workspace, plan.integration_id)
    work = workspace.work_item(plan.work_item_id)
    if work is None:
        raise WorkspaceError(f"work item not found: {plan.work_item_id}")
    _assert_human_can_decide_plan(human, work, integration, plan)

    records = store.data.setdefault("integration_outbox", [])
    if not isinstance(records, list):
        raise WorkspaceError("integration_outbox must be a list of objects")
    duplicate = next(
        (item for item in records if isinstance(item, dict) and item.get("plan_id") == plan.id),
        None,
    )
    if duplicate is not None:
        raise WorkspaceError(
            f"integration plan {plan.id} is already enqueued as {duplicate.get('id')}"
        )

    timestamp = _timestamp()
    record = {
        "id": _generated_outbox_id(plan.id, timestamp),
        "plan_id": plan.id,
        "integration_id": plan.integration_id,
        "work_item_id": plan.work_item_id,
        "event": plan.event,
        "action": plan.action,
        "enqueued_by": human.id,
        "status": "queued",
        "payload_preview": deepcopy(plan.payload_preview),
        "source_boundary": deepcopy(plan.source_boundary),
        "risk": plan.risk,
        "timestamp": timestamp,
        "notes": "Queued for a future execution boundary only. No provider call was made.",
    }
    records.append(record)
    workspace = write_store(store)
    history_event = append_history_event(
        store.data_path,
        schema_version=workspace.schema_version,
        command="integration enqueue",
        action="queued",
        object_type="integration-outbox",
        object_collection="integration_outbox",
        object_id=str(record["id"]),
        actor=human.id,
        before=None,
        after=record,
    )
    return {
        "workspace": workspace.name,
        "dry_run": True,
        "would_call_provider": False,
        "status": "queued",
        "integration_outbox_item": record,
        "integration_plan": to_plain(plan),
        "human": {
            "id": human.id,
            "name": human.name,
            "authority_level": human.authority_level,
            "approval_capabilities": human.approval_capabilities,
        },
        "history_event": history_event,
        "next_action": "Outbox item queued for future execution wiring; no provider call was made.",
    }


def _integration_summary(integration: Integration) -> dict[str, Any]:
    return {
        "id": integration.id,
        "provider": integration.provider,
        "label": integration.label,
        "mode": integration.mode,
        "owner_human": integration.owner_human,
        "enabled": integration.enabled,
        "allowed_events": integration.allowed_events,
        "allowed_actions": integration.allowed_actions,
        "risk_level": integration.risk_level,
        "source_ids": integration.source_ids,
        "secret_ref": integration.secret_ref,
        "notes": integration.notes,
    }


def _assert_human_can_decide_plan(
    human: Human,
    work: WorkItem,
    integration: Integration,
    plan: IntegrationPlan,
) -> None:
    if _human_can_decide_plan(human, work, integration):
        return
    if work.required_approval_capability:
        expected = work.required_approval_capability
    elif integration.risk_level in {"high", "critical"}:
        expected = "policy, deploy, or security capability"
    else:
        expected = f"integration owner {integration.owner_human} or relevant approval capability"
    raise WorkspaceError(
        f"human {human.id} lacks authority to decide integration plan {plan.id}; "
        f"expected {expected}"
    )


def _human_can_decide_plan(
    human: Human,
    work: WorkItem,
    integration: Integration,
) -> bool:
    if human.authority_level == "admin":
        return True
    if work.required_approval_capability:
        return work.required_approval_capability in human.approval_capabilities
    if integration.owner_human == human.id and integration.risk_level in {"low", "standard"}:
        return True
    if integration.risk_level in {"high", "critical"}:
        return bool({"policy", "deploy", "security"} & set(human.approval_capabilities))
    return bool(
        {"operations", "product", "policy", "merge", "deploy"} & set(human.approval_capabilities)
    )


def _decision_next_action(status: str) -> str:
    if status == "approved":
        return "Approved for future execution wiring only; no provider call was made."
    if status == "rejected":
        return "Plan rejected. Create a new dry-run plan if the external action changes."
    return "Plan canceled. No external action is pending for this plan."


def _integration_or_raise(workspace: Workspace, integration_id: str) -> Integration:
    integration = workspace.integration(integration_id)
    if integration is None:
        known = ", ".join(sorted(item.id for item in workspace.integrations))
        raise WorkspaceError(f"integration not found: {integration_id}; known integrations: {known}")
    return integration


def _assert_can_plan(integration: Integration, event: str, action: str) -> None:
    if not integration.enabled:
        raise WorkspaceError(f"integration {integration.id} is disabled; dry-run planning is blocked")
    if event not in integration.allowed_events:
        raise WorkspaceError(
            f"integration {integration.id} does not allow event {event}; "
            f"allowed events: {', '.join(integration.allowed_events)}"
        )
    if action not in integration.allowed_actions:
        raise WorkspaceError(
            f"integration {integration.id} does not allow action {action}; "
            f"allowed actions: {', '.join(integration.allowed_actions)}"
        )
    supported = PROVIDER_ACTIONS.get(integration.provider, set())
    if action not in supported:
        raise WorkspaceError(
            f"integration {integration.id} provider {integration.provider} "
            f"does not support action {action}"
        )


def _payload_preview(
    workspace: Workspace,
    integration: Integration,
    work: WorkItem,
    event: str,
    action: str,
) -> dict[str, Any]:
    summary = _work_summary(workspace, work, event)
    if integration.provider == "slack":
        return {
            "provider": "slack",
            "operation": "post_message",
            "webhook_ref": integration.secret_ref,
            "json": {
                "text": summary,
                "blocks": [
                    {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Dry run only. Work: {work.id}. Event: {event}.",
                            }
                        ],
                    },
                ],
            },
        }
    if integration.provider == "github":
        return {
            "provider": "github",
            "operation": _github_operation(action),
            "repository_ref": "configured outside Palari",
            "json": {
                "title": f"[Palari] {event}: {work.title}",
                "body": summary,
                "labels": ["palari", "dry-run", event],
            },
        }
    if integration.provider == "jira":
        return {
            "provider": "jira",
            "operation": _jira_operation(action),
            "project_ref": "configured outside Palari",
            "json": {
                "summary": f"[Palari] {event}: {work.title}",
                "description": summary,
                "labels": ["palari", "dry-run", event],
            },
        }
    if integration.provider == "email":
        return {
            "provider": "email",
            "operation": "draft_notification",
            "transport_ref": integration.secret_ref,
            "json": {
                "subject": f"[Palari] {event}: {work.title}",
                "body": summary,
            },
        }
    raise WorkspaceError(f"unsupported integration provider: {integration.provider}")


def _work_summary(workspace: Workspace, work: WorkItem, event: str) -> str:
    palari = workspace.palari(work.palari)
    goal = workspace.goal(work.goal)
    return (
        f"{event}: {work.id} {work.title}. "
        f"Status {work.status}; risk {work.risk}; "
        f"Palari {palari.name if palari else work.palari}; "
        f"goal {goal.title if goal else work.goal}."
    )


def _github_operation(action: str) -> str:
    if action == "create_issue":
        return "create_issue"
    if action == "comment":
        return "create_issue_comment"
    return "create_notification_issue_preview"


def _jira_operation(action: str) -> str:
    if action == "create_issue":
        return "create_issue"
    if action == "update_issue":
        return "update_issue"
    if action == "comment":
        return "add_comment"
    return "create_notification_issue_preview"


def _source_boundary(
    workspace: Workspace,
    integration: Integration,
    work: WorkItem,
) -> dict[str, Any]:
    integration_sources = set(integration.source_ids)
    work_sources = set(work.allowed_sources)
    shared = sorted(integration_sources & work_sources)
    return {
        "integration_sources": sorted(integration_sources),
        "work_allowed_sources": sorted(work_sources),
        "shared_sources": shared,
        "shared_source_labels": [
            workspace.source(source_id).label
            for source_id in shared
            if workspace.source(source_id) is not None
        ],
    }


def _plan_record(
    preview: dict[str, Any],
    integration: Integration,
    work: WorkItem,
    *,
    actor: str,
    plan_id: str,
) -> dict[str, Any]:
    timestamp = _timestamp()
    return {
        "id": plan_id or _generated_plan_id(timestamp),
        "integration_id": integration.id,
        "work_item_id": work.id,
        "event": str(preview["event"]),
        "action": str(preview["action"]),
        "actor": actor or work.palari,
        "status": "pending-approval",
        "payload_preview": preview["payload_preview"],
        "source_boundary": preview["safety"]["source_boundary"],
        "risk": integration.risk_level,
        "approval_required": True,
        "timestamp": timestamp,
        "notes": "Dry-run only. No provider call was made and no secret value was read.",
    }


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _generated_plan_id(timestamp: str) -> str:
    compact = timestamp.replace("-", "").replace(":", "").replace("Z", "Z")
    return f"PLAN-{compact}-{uuid.uuid4().hex[:8].upper()}"


def _generated_outbox_id(plan_id: str, timestamp: str) -> str:
    compact = timestamp.replace("-", "").replace(":", "").replace("Z", "Z")
    safe_plan = "".join(ch if ch.isalnum() else "-" for ch in plan_id).strip("-")
    return f"OUTBOX-{safe_plan}-{compact}-{uuid.uuid4().hex[:6].upper()}"
